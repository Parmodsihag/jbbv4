"""The chat assistant: language, periods, names, asking back, tools, models, training cell."""

from __future__ import annotations

import datetime as dt
import json
import zipfile

import pytest

from hth.assistant import data
from hth.assistant import normalize as norm
from hth.assistant.core import Assistant, Session, route
from hth.assistant.entities import EntityIndex, resolve_choice
from hth.assistant.system1 import IntentClassifier, concept, evaluate
from hth.assistant.system2 import LocalModel, find_model, install_zip
from hth.assistant.tools import TOOLS

TODAY = dt.date(2026, 10, 20)


@pytest.fixture(scope="module")
def classifier():
    train, _test = data.split(data.generate(per_template=30))
    return IntentClassifier.train(train)


@pytest.fixture
def shop(db, accounts, inventory, sales, krar):
    r1 = accounts.add_customer("RAMESH KUMAR", "ROHTAK", 5000, "2026-09-01")
    r2 = accounts.add_customer("RAMESH SAINI", "BHIWANI 9812345678", 1200, "2026-09-03")
    r3 = accounts.add_customer("RAMESH GODARA", "HISAR", 0, "2026-09-05")
    s = accounts.add_customer("SURESH JAKHAR", "SIRSA", 800, "2026-08-01")
    urea = inventory.add_item("UREA", 266, 280, unit="BAG", opening_quantity=40)
    dap = inventory.add_item("DAP", 1350, 1400, unit="BAG", opening_quantity=4)
    sales.record("P", "2026-09-10", r1.id, "UREA", 5, 280, 1, "admin", item_id=urea.id)
    sales.record("P", "2026-10-19", s.id, "DAP", 2, 1400, 1, "admin", item_id=dap.id)
    accounts.add_transaction(r2.id, "2026-10-19", "CASH RECEIVED", 500, "M", 2)
    krar.add_or_update(r1.id, "2026-10-10")
    krar.add_or_update(s.id, "2026-10-25")
    return {"r1": r1, "r2": r2, "r3": r3, "s": s, "urea": urea, "dap": dap}


@pytest.fixture
def bot(db, shop, classifier):
    return Assistant(db, today=TODAY, classifier=classifier)


# Language and periods ------------------------------------------------------------------------
def test_language_follows_the_question():
    assert norm.language("रमेश का कितना बकाया है") == "hi"
    assert norm.language("ramesh ka kitna baaki hai") == "hl"
    assert norm.language("how much does ramesh owe") == "en"
    assert norm.answer_language("ramesh ka hisab btao") == "hi"
    assert norm.answer_language("show me the ledger") == "en"


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("pichle mahine ki bikri", "last_month"),
        ("पिछले महीने का हिसाब", "last_month"),
        ("sales last month", "last_month"),
        ("is hafte", "this_week"),
        ("aaj ka hisab", "today"),
        ("kal kitna bika", "yesterday"),
        ("is saal ka munafa", "this_fy"),
    ],
)
def test_periods(text, value):
    p = norm.find_period(text, TODAY)
    assert p is not None and p.value == value


def test_may_is_not_a_month_in_may_i_know():
    assert norm.find_period("may i know the stock of urea", TODAY) is None


def test_last_month_dates():
    p = norm.find_period("last month", TODAY)
    assert (p.start, p.end) == (dt.date(2026, 9, 1), dt.date(2026, 9, 30))


# Names -------------------------------------------------------------------------------------
def test_three_rameshes_are_ambiguous_and_a_village_settles_it(db, shop):
    index = EntityIndex.from_db(db, TODAY)
    mention = index.link("Ramesh ka hisab").first("customer")
    assert mention.ambiguous and len(mention.candidates) == 3
    assert resolve_choice("rohtak wala", mention.candidates).id == shop["r1"].id
    assert resolve_choice("dusra", mention.candidates) is not None
    assert resolve_choice("5678", mention.candidates).id == shop["r2"].id


def test_full_names_devanagari_and_typos_link(db, shop):
    index = EntityIndex.from_db(db, TODAY)
    assert index.link("ramesh godara ka phone").first("customer").best.id == shop["r3"].id
    assert index.link("रमेश सैनी का बकाया").first("customer").best.id == shop["r2"].id
    assert index.link("suresh jakar").first("customer").best.id == shop["s"].id
    assert index.link("urea kitna bacha").first("item").best.id == shop["urea"].id


# Dialog -------------------------------------------------------------------------------------
def test_ask_back_with_names_then_answer_and_forget(bot, shop):
    session = Session()
    reply = bot.ask("Ramesh ka last month ka hisab btao", session)
    assert reply.kind == "ask" and reply.lang == "hi"
    assert len(reply.options) == 3 and "रमेश" in reply.text
    reply = bot.ask("rohtak wala", session)
    assert reply.kind == "answer" and reply.tool == "customer_ledger"
    assert reply.args["customer"] == shop["r1"].id and reply.args["period"].value == "last_month"
    assert session.pending is None  # settled: the question left the context


def test_pick_by_number_and_english_answer(bot, shop):
    session = Session()
    reply = bot.ask("how much does ramesh owe", session)
    assert reply.kind == "ask" and reply.lang == "en"
    picked = next(o for o in reply.options if "Saini" in o.label)
    reply = bot.ask(picked.reply, session)
    assert reply.kind == "answer" and reply.tool == "customer_balance" and reply.lang == "en"
    assert "owes us" in reply.text


def test_cancel_clears_the_open_question(bot, shop):
    session = Session()
    bot.ask("ramesh", session)
    assert session.pending is not None
    reply = bot.ask("chhodo", session)
    assert reply.kind == "cancelled" and session.pending is None


def test_missing_customer_is_asked_for(bot, shop):
    session = Session()
    reply = bot.ask("kab paise dega?", session)
    if reply.kind == "ask":  # the customer is required: asked, then answered
        reply = bot.ask("suresh", session)
    assert reply.kind == "answer"


def test_follow_ups_reuse_the_last_question(bot, shop):
    session = Session()
    assert bot.ask("is mahine ki bikri", session).tool == "period_sales"
    reply = bot.ask("aur pichle mahine?", session)
    assert reply.tool == "period_sales" and reply.source == "followup"
    assert reply.args["period"].value == "last_month"
    bot.ask("how much does ramesh saini owe", session)
    reply = bot.ask("and suresh?", session)
    assert reply.tool == "customer_balance" and reply.args["customer"] == shop["s"].id
    reply = bot.ask("uska phone number", session)
    assert reply.tool == "customer_contact" and reply.args["customer"] == shop["s"].id


@pytest.mark.parametrize(
    ("question", "tool"),
    [
        ("urea kitna bacha hai", "item_stock"),
        ("dap ka bhav", "item_price"),
        ("kal kitni bikri hui", "day_summary"),
        ("pichle mahine kitni bikri hui", "period_sales"),
        ("kiske karar ki tarikh nikal gayi", "krar_overdue"),
        ("sabse bade 5 bakayedar", "top_debtors"),
        ("bazar me kul kitna udhaar hai", "total_receivable"),
        ("kal ki entry dikhao", "day_book"),
        ("what should I reorder", "reorder"),
        ("suresh kab paise dega", "customer_krar"),
        ("इस साल कितना मुनाफ़ा हुआ", "profit"),
    ],
)
def test_everyday_questions(bot, question, tool):
    reply = bot.ask(question, Session())
    assert reply.kind == "answer", (question, reply.kind, reply.text)
    assert reply.tool == tool


def test_help_greeting_and_off_topic(bot):
    assert bot.ask("kya kya puch sakte hain", Session()).kind == "help"
    assert bot.ask("namaste", Session()).kind == "greeting"
    assert bot.ask("sone ka bhav kya hai", Session()).kind == "decline"


def test_employee_sees_only_what_their_role_allows(db, shop, classifier, auth):
    employee = next(u for u in auth.list_users() if u.username == "emp1")
    reply = Assistant(db, employee, today=TODAY, classifier=classifier).ask("is saal ka munafa", Session())
    assert reply.kind == "decline"


def test_answers_are_read_only_and_audited_without_the_question(db, bot, shop):
    def snapshot():
        return (
            db.fetchone("SELECT count(*) n, coalesce(sum(amount), 0) s FROM transactions")[:],
            db.fetchone("SELECT count(*) n FROM customers")[:],
            db.fetchone("SELECT count(*) n FROM krar")[:],
        )

    before = snapshot()
    session = Session()
    for q in ["Ramesh ka hisab", "2", "urea kitna bacha", "collection list", "kya mangwana hai", "aaj ka hisab"]:
        bot.ask(q, session)
    assert snapshot() == before
    logged = [r["message"] for r in db.fetchall("SELECT message FROM audit_log WHERE code = '13'")]
    assert logged and all(m.startswith("assistant ") for m in logged)
    assert not any("Ramesh" in m or "rohtak" in m.lower() for m in logged)


def test_every_tool_answers_in_both_languages(db, shop):
    from hth.assistant.tools import Services

    svc = Services(db)
    args = {
        "customer": shop["r1"].id,
        "item": shop["urea"].id,
        "period": norm.resolve("last_month", TODAY),
        "day": norm.resolve("yesterday", TODAY),
        "number": 5,
    }
    for name, tool in TOOLS.items():
        a = {s.name: args[s.name] for s in tool.slots if s.name in args}
        for lang in ("en", "hi"):
            ans = tool.run(svc, a, lang, TODAY)
            assert ans.headline, name
            for row in ans.rows:
                assert len(row) >= len(ans.columns), name


# System 1 -----------------------------------------------------------------------------------
def test_system1_accuracy_on_unseen_phrasings(classifier):
    _train, test = data.split(data.generate(per_template=30))
    assert evaluate(classifier, test)["accuracy"] >= 0.88
    routed = sum(route(classifier, e.text, TODAY)[0][0] == e.intent for e in test) / len(test)
    assert routed >= 0.9


def test_typos_still_name_the_concept():
    assert concept("prfoit") == concept("profit")
    assert concept("phonee") == concept("phone")
    assert concept("this") is None  # common words never match a concept by accident


def test_classifier_cache_round_trip(tmp_path, classifier):
    path = tmp_path / "s1.npz"
    classifier.save(path)
    loaded = IntentClassifier.load(path)
    assert loaded.predict("<C1> ka kitna baaki hai").intent == classifier.predict("<C1> ka kitna baaki hai").intent


# Training data ------------------------------------------------------------------------------
def test_targets_round_trip_and_hold_no_names():
    examples = data.generate(per_template=4)
    for e in examples:
        assert data.parse_call(data.target(e.intent, e.args)) == (e.intent, e.args)
        assert "{" not in e.text and "}" not in e.text
    assert all(e.intent in data.INTENTS for e in examples)
    assert "<C1>" in data.prompt("<C1> ka hisab")


def test_kaggle_cell_is_up_to_date():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "tools" / "assistant" / "build_kaggle_cell.py"
    spec = importlib.util.spec_from_file_location("build_kaggle_cell", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    cell = builder.CELL.read_text(encoding="utf-8")
    assert cell == builder.build(), "run python tools/assistant/build_kaggle_cell.py"
    compile(cell, str(builder.CELL), "exec")
    from hth.assistant.core import CONFIDENT

    assert f"S1_CONFIDENT = {CONFIDENT}" in cell  # the cell judges System 2 by the app's own threshold


# System 2 -----------------------------------------------------------------------------------
def _fake_model_folder(folder, version=data.PROMPT_VERSION):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "hth-assistant-q4_k_m.gguf").write_bytes(b"GGUF fake")
    (folder / "manifest.json").write_text(json.dumps({"prompt_version": version, "base_model": "test"}))
    return folder


def _answering(intent, seen=None):
    def loader(path, threads, ctx):
        def run(prompt):
            if seen is not None:
                seen.append(prompt)
            return f"<start_function_call>call:{intent}{{}}<end_function_call>"

        return run

    return loader


UNCLEAR = "zxq vbnm plok"  # System 1 cannot place it


def test_system2_is_used_only_when_system1_is_unsure(db, shop, classifier, tmp_path):
    top3 = [i for i, _p in route(classifier, UNCLEAR, TODAY)[:3]]
    pick = next(i for i in top3 if i in TOOLS)
    seen = []
    model = LocalModel(_fake_model_folder(tmp_path / "models"), loader=_answering(pick, seen), idle_seconds=60)
    bot = Assistant(db, today=TODAY, classifier=classifier, system2=model)
    assert bot.ask("urea kitna bacha hai", Session()).source == "system1"
    assert not seen
    reply = bot.ask(UNCLEAR, Session())
    assert seen and "<start_of_turn>user" in seen[0]
    assert reply.tool == pick and reply.source == "system2"
    model.unload()
    assert not model.loaded


def test_system2_outside_system1s_top_three_is_asked_back(db, shop, classifier, tmp_path):
    top3 = {i for i, _p in route(classifier, UNCLEAR, TODAY)[:3]}
    outsider = next(i for i in TOOLS if i not in top3)
    model = LocalModel(_fake_model_folder(tmp_path / "models"), loader=_answering(outsider))
    reply = Assistant(db, today=TODAY, classifier=classifier, system2=model).ask(UNCLEAR, Session())
    assert reply.kind == "unsure" and reply.tool != outsider


def _echo_factory(path, threads, ctx):
    return lambda prompt: "<start_function_call>call:reorder{}<end_function_call>"


def _crashing_factory(path, threads, ctx):
    import os

    os._exit(3)  # what an "illegal instruction" in llama.cpp looks like from outside


def test_model_runs_in_its_own_process(tmp_path):
    from hth.assistant.system2 import ProcessRunner

    runner = ProcessRunner(tmp_path / "m.gguf", 1, 64, factory=_echo_factory)
    try:
        assert data.parse_call(runner(data.prompt("<C1> ka hisab"))) == ("reorder", {})
    finally:
        runner.close()


def test_a_crashing_model_process_only_switches_system2_off(db, shop, classifier, tmp_path):
    from hth.assistant.system2 import ProcessRunner

    def loader(path, threads, ctx):
        return ProcessRunner(path, threads, ctx, factory=_crashing_factory)

    model = LocalModel(_fake_model_folder(tmp_path / "models"), loader=loader)
    reply = Assistant(db, today=TODAY, classifier=classifier, system2=model).ask(UNCLEAR, Session())
    assert reply.kind == "unsure"  # this process is alive and still answering
    assert "exit code 3" in model.error and not model.available()


def test_broken_model_falls_back_quietly(db, shop, classifier, tmp_path):
    def loader(path, threads, ctx):
        raise RuntimeError("illegal instruction")

    model = LocalModel(_fake_model_folder(tmp_path / "models"), loader=loader)
    bot = Assistant(db, today=TODAY, classifier=classifier, system2=model)
    reply = bot.ask("zxq vbnm plok", Session())
    assert reply.kind in ("unsure", "answer", "decline")
    assert model.error and not model.available()


def test_install_zip_takes_only_model_files(tmp_path):
    src = tmp_path / "m.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("hth_assistant_model/manifest.json", json.dumps({"prompt_version": data.PROMPT_VERSION}))
        z.writestr("hth_assistant_model/hth-assistant-q8_0.gguf", b"GGUF")
        z.writestr("hth_assistant_model/hth-assistant-q4_k_m.gguf", b"GGUF")
        z.writestr("../../evil.gguf", b"x")
        z.writestr("adapter/adapter_model.safetensors", b"x")
    data_dir = tmp_path / "data"
    info = install_zip(src, data_dir)
    assert info.path.parent == data_dir / "models"
    # only the file the app would use, plus the manifest
    assert sorted(p.name for p in (data_dir / "models").iterdir()) == ["hth-assistant-q4_k_m.gguf", "manifest.json"]
    assert not (tmp_path / "evil.gguf").exists()


def test_install_zip_refuses_a_model_for_another_prompt(tmp_path):
    src = tmp_path / "m.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("manifest.json", json.dumps({"prompt_version": data.PROMPT_VERSION + 1}))
        z.writestr("a.gguf", b"GGUF")
    with pytest.raises(ValueError):
        install_zip(src, tmp_path / "data")
    assert find_model(_fake_model_folder(tmp_path / "old", version=99)) is None
