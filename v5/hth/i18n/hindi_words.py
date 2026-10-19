"""Word lists for :mod:`hth.i18n.translit` (Roman spelling -> Devanagari).

General vocabulary only - common North-Indian given names, Haryana / Rajasthan surnames
and gotras, name endings, agri-input brands, crops and units - including the informal
spellings used at shop counters (PARKASH, SUBASH, MAHABIR).  Anything missing falls back to
the phonetic rules and can be corrected per record in the app.
"""

from __future__ import annotations

# fmt: off
NAME_WORDS: dict[str, str] = {
    # given names - men
    "RAM": "राम", "RAMA": "रामा", "SHYAM": "श्याम", "MOHAN": "मोहन", "SOHAN": "सोहन", "ROHAN": "रोहन",
    "KRISHAN": "कृष्ण", "KRISHNA": "कृष्णा", "KISHAN": "किशन", "KISHOR": "किशोर", "KISHORE": "किशोर",
    "RAMESH": "रमेश", "SURESH": "सुरेश", "MAHESH": "महेश", "MUKESH": "मुकेश", "RAJESH": "राजेश",
    "NARESH": "नरेश", "DINESH": "दिनेश", "GANESH": "गणेश", "UMESH": "उमेश", "YOGESH": "योगेश",
    "RITESH": "रितेश", "NILESH": "नीलेश", "KAMLESH": "कमलेश", "BRIJESH": "बृजेश", "SURJIT": "सुरजीत",
    "SUBASH": "सुभाष", "SUBHASH": "सुभाष", "SUBHAS": "सुभाष", "PARKASH": "प्रकाश", "PRAKASH": "प्रकाश",
    "OM": "ओम", "OMPARKASH": "ओमप्रकाश", "OMPRAKASH": "ओमप्रकाश", "JAGDISH": "जगदीश", "JADISH": "जगदीश",
    "MAHABIR": "महाबीर", "MAHAVIR": "महावीर", "MAHAVEER": "महावीर", "HANUMAN": "हनुमान",
    "BALWAN": "बलवान", "BALWANT": "बलवंत", "BALBIR": "बलबीर", "BALRAJ": "बलराज", "BALDEV": "बलदेव",
    "RANBIR": "रणबीर", "SATBIR": "सतबीर", "SATPAL": "सतपाल", "DHARAMBIR": "धर्मबीर", "DHARMBIR": "धर्मबीर",
    "DHARMPAL": "धर्मपाल", "DHARAMPAL": "धर्मपाल", "JAIBIR": "जयबीर", "JAIPAL": "जयपाल", "JAI": "जय",
    "SOMBIR": "सोमबीर", "SOMPAL": "सोमपाल", "RAJBIR": "राजबीर", "RAJPAL": "राजपाल", "JASBIR": "जसबीर",
    "RAJENDER": "राजेंद्र", "RAJINDER": "राजेंद्र", "RAJENDRA": "राजेंद्र", "SURENDER": "सुरेंद्र",
    "SURINDER": "सुरेंद्र", "MAHENDER": "महेंद्र", "MAHINDER": "महेंद्र", "NARENDER": "नरेंद्र",
    "VIRENDER": "वीरेंद्र", "BIJENDER": "बिजेंद्र", "JOGINDER": "जोगिंदर", "JITENDER": "जितेंद्र",
    "DHARMENDER": "धर्मेंद्र", "DEVENDER": "देवेंद्र", "RAVINDER": "रविंदर", "HARINDER": "हरिंदर",
    "INDER": "इंदर", "SATENDER": "सतेंद्र", "PAWAN": "पवन", "PAVAN": "पवन", "SUNIL": "सुनील",
    "ANIL": "अनिल", "SANJAY": "संजय", "SANJEEV": "संजीव", "VIJAY": "विजय", "AJAY": "अजय",
    "AMIT": "अमित", "SUMIT": "सुमित", "ROHIT": "रोहित", "MOHIT": "मोहित", "SACHIN": "सचिन",
    "DEEPAK": "दीपक", "DEPAK": "दीपक", "DIPAK": "दीपक", "MANOJ": "मनोज", "VINOD": "विनोद",
    "PRAMOD": "प्रमोद", "SANDEEP": "संदीप", "SANDIP": "संदीप", "KULDEEP": "कुलदीप", "KULDIP": "कुलदीप",
    "PRADEEP": "प्रदीप", "PARDEEP": "प्रदीप", "PARDIP": "प्रदीप", "RAJ": "राज", "RAJU": "राजू",
    "RAVI": "रवि", "SUNNY": "सनी", "MONU": "मोनू", "SONU": "सोनू", "BABLU": "बबलू", "PAPPU": "पप्पू",
    "PAPU": "पप्पू", "TINKU": "टिंकू", "PINTU": "पिंटू", "BITTU": "बिट्टू", "GOLU": "गोलू", "LALU": "लालू",
    "LILU": "लीलू", "LACHU": "लच्छू", "BHOLA": "भोला", "CHHOTU": "छोटू", "CHOTU": "छोटू",
    "CHOTURAM": "छोटूराम", "CHHOTURAM": "छोटूराम", "SITARAM": "सीताराम", "SITA": "सीता",
    "RAMNIWAS": "रामनिवास", "RAMNIVAS": "रामनिवास", "NIWAS": "निवास", "RAMKUMAR": "रामकुमार",
    "RAMPHAL": "रामफल", "RAMCHANDER": "रामचंद्र", "RAMCHANDRA": "रामचंद्र", "RAMSWAROOP": "रामस्वरूप",
    "RAMSARUP": "रामस्वरूप", "RAMPAL": "रामपाल", "RAMDHARI": "रामधारी", "RAMDIYA": "रामदिया",
    "LALCHAND": "लालचंद", "HUKAMCHAND": "हुकमचंद", "PREMCHAND": "प्रेमचंद", "TARACHAND": "ताराचंद",
    "KHEMCHAND": "खेमचंद", "AMICHAND": "अमीचंद", "MANGAL": "मंगल", "MANGLA": "मंगला",
    "CHANDERBHAN": "चंद्रभान", "CHANDER": "चंद्र", "CHANDRA": "चंद्र", "BHAN": "भान",
    "BHAGIRATH": "भागीरथ", "BHAGAT": "भगत", "BHAGWAN": "भगवान", "BHAGWANA": "भगवाना",
    "BANSI": "बंसी", "BANSILAL": "बंसीलाल", "HARI": "हरि", "HARIRAM": "हरिराम", "HARISINGH": "हरिसिंह",
    "HARSINGH": "हरसिंह", "HAR": "हर", "MAN": "मान", "MANSINGH": "मानसिंह", "AMAR": "अमर",
    "AMARSINGH": "अमरसिंह", "BHUP": "भूप", "BHUPSINGH": "भूपसिंह", "BHUPENDER": "भूपेंद्र",
    "UMED": "उमेद", "UMEDSINGH": "उमेदसिंह", "RANJEET": "रणजीत", "RANJIT": "रणजीत", "SARJEET": "सरजीत",
    "SURJEET": "सुरजीत", "SURAJ": "सूरज", "SURAJMAL": "सूरजमल", "SUKHBIR": "सुखबीर", "SUKHDEV": "सुखदेव",
    "SUKHA": "सुखा", "DALBIR": "दलबीर", "DALIP": "दलीप", "DILBAG": "दिलबाग", "ISHWAR": "ईश्वर",
    "ISHAR": "ईशर", "ISHWER": "ईश्वर", "MANPHOOL": "मनफूल", "MANFUL": "मनफूल", "MANPHUL": "मनफूल",
    "MANFOOL": "मनफूल", "PHOOL": "फूल", "FULSINGH": "फूलसिंह", "PHOOLSINGH": "फूलसिंह",
    "DAYANAND": "दयानंद", "SADANAND": "सदानंद", "ANAND": "आनंद", "AMILAL": "अमीलाल", "HETRAM": "हेतराम",
    "NETRAM": "नेतराम", "PATRAM": "पतराम", "MOTIRAM": "मोतीराम", "MOTI": "मोती", "MANIRAM": "मनीराम",
    "DAIRAM": "दईराम", "DULARAM": "दूलाराम", "BUDHRAM": "बुधराम", "BHOGARAM": "भोगाराम", "JITRAM": "जीतराम",
    "BHAHNIRAM": "भानीराम", "BHANIRAM": "भानीराम", "SURTARAM": "सुरताराम", "KALU": "कालू", "KALURAM": "कालूराम",
    "CHABILDAS": "छबीलदास", "CHHABILDAS": "छबीलदास", "TULSI": "तुलसी", "TULSIRAM": "तुलसीराम",
    "SANTKUMAR": "संतकुमार", "SANT": "संत", "NIHAL": "निहाल", "NIHALSINGH": "निहालसिंह",
    "MEHAR": "मेहर", "MEHARSINGH": "मेहरसिंह", "SHEO": "शिव", "SHIV": "शिव", "SHIVKUMAR": "शिवकुमार",
    "SHAMSHER": "शमशेर", "SAMSHER": "शमशेर", "SUBE": "सुबे", "SUBESINGH": "सूबेसिंह",
    "SUBHESINGH": "सूबेसिंह", "THAKERDAS": "ठाकरदास", "RAMJILAL": "रामजीलाल", "JILAL": "जीलाल",
    "BAJRANG": "बजरंग", "BHIM": "भीम", "BHEEM": "भीम", "BHOOP": "भूप", "ATMA": "आत्मा", "ATMARAM": "आत्माराम",
    "NAVEEN": "नवीन", "NAVEN": "नवीन", "NAVIN": "नवीन", "PRAVEEN": "प्रवीण", "PARVEEN": "प्रवीण",
    "RAKESH": "राकेश", "RAJKUMAR": "राजकुमार", "ASHOK": "अशोक", "ARUN": "अरुण", "VARUN": "वरुण",
    "VIKAS": "विकास", "VIKASH": "विकास", "AKASH": "आकाश", "ANKIT": "अंकित", "ANKUR": "अंकुर",
    "MANISH": "मनीष", "MONIKA": "मोनिका", "NITIN": "नितिन", "GAURAV": "गौरव", "SAURABH": "सौरभ",
    "VISHAL": "विशाल", "KAPIL": "कपिल", "KULDEEPSINGH": "कुलदीपसिंह", "HARPAL": "हरपाल", "MAHAVIRSINGH": "महावीरसिंह",
    "TARA": "तारा", "PREM": "प्रेम", "HUKAM": "हुकम", "KHEM": "खेम", "DAYA": "दया", "JAGAT": "जगत",
    "JAGMAL": "जगमल", "JAGBIR": "जगबीर", "JAGDEEP": "जगदीप", "JAGJEET": "जगजीत", "MAMAN": "मामन",
    "MAMCHAND": "मामचंद", "MOHINDER": "मोहिंदर", "KARTAR": "करतार", "KARAMBIR": "करमबीर",
    "KARAMVIR": "करमवीर", "KARAMCHAND": "करमचंद", "KARAN": "करण", "ARJUN": "अर्जुन", "LAXMAN": "लक्ष्मण",
    "LAKHAN": "लखन", "LAKHMI": "लखमी", "LEKHRAM": "लेखराम", "PARMOD": "प्रमोद", "PARMOOD": "प्रमोद",
    "PARMESHWAR": "परमेश्वर", "GOPAL": "गोपाल", "GOVIND": "गोविंद", "GOBIND": "गोबिंद", "NANAK": "नानक",
    "NAND": "नंद", "NANDLAL": "नंदलाल", "MADAN": "मदन", "MADANLAL": "मदनलाल", "MURARI": "मुरारी",
    "MURARILAL": "मुरारीलाल", "SHANKAR": "शंकर", "MAHADEV": "महादेव", "DEVI": "देवी", "DEVILAL": "देवीलाल",
    "DEV": "देव", "DUTT": "दत्त", "DATT": "दत्त", "INDRAJ": "इंद्राज", "INDERJEET": "इंद्रजीत",
    "SHRI": "श्री", "SRI": "श्री", "JI": "जी", "BHAI": "भाई", "BABA": "बाबा", "BABU": "बाबू", "LALA": "लाला",
    "DADA": "दादा", "CHACHA": "चाचा", "TAU": "ताऊ", "MAMA": "मामा", "FOJI": "फौजी", "FAUJI": "फौजी",
    "MASTER": "मास्टर", "SARPANCH": "सरपंच", "PATWARI": "पटवारी", "MISTRI": "मिस्त्री", "DOCTOR": "डॉक्टर",
    "DR": "डॉ", "MEMBER": "मेंबर", "THEKEDAR": "ठेकेदार", "PANDIT": "पंडित", "SETH": "सेठ",
    "MAHANT": "महंत", "SAHAB": "साहब", "SAHIB": "साहिब",
    # women
    "SUNITA": "सुनीता", "ANITA": "अनीता", "KAMLA": "कमला", "BIMLA": "बिमला", "VIMLA": "विमला",
    "SHANTI": "शांति", "SAROJ": "सरोज", "SANTOSH": "संतोष", "SUMAN": "सुमन", "SAVITRI": "सावित्री",
    "RAMPYARI": "रामप्यारी", "PREMLATA": "प्रेमलता", "KAILASHO": "कैलाशो", "KAILASH": "कैलाश",
    "SUSHILA": "सुशीला", "URMILA": "उर्मिला", "NIRMALA": "निर्मला", "PUSHPA": "पुष्पा", "MAYA": "माया",
    "GEETA": "गीता", "SEEMA": "सीमा", "REKHA": "रेखा", "POONAM": "पूनम", "PINKY": "पिंकी", "RAJBALA": "राजबाला",
    "BALA": "बाला", "WATI": "वती", "BAI": "बाई",
    # surnames, gotras, communities
    "SINGH": "सिंह", "KUMAR": "कुमार", "LAL": "लाल", "CHAND": "चंद", "DAS": "दास", "PAL": "पाल",
    "VERMA": "वर्मा", "SHARMA": "शर्मा", "YADAV": "यादव", "SAINI": "सैनी", "SIHAG": "सिहाग",
    "SIYAG": "सियाग", "GODARA": "गोदारा", "BENIWAL": "बेनीवाल", "JAKHAR": "जाखड़", "JAKHAD": "जाखड़",
    "BISHNOI": "बिश्नोई", "BHADU": "भादू", "PONIA": "पूनिया", "PUNIA": "पूनिया", "POONIA": "पूनिया",
    "JANGU": "जांगू", "JANGRA": "जांगड़ा", "JANGIR": "जांगिड़", "SHARAN": "शरण", "SAHARAN": "सहारण",
    "KASWAN": "कस्वां", "DUDI": "डूडी", "KHICHAR": "खीचड़", "BHAMBHU": "भांभू", "BHAMBU": "भांभू",
    "DHAKA": "ढाका", "TARAD": "तरड़", "MANDA": "मांडा", "LAMBA": "लांबा", "NAIN": "नैन", "GILL": "गिल",
    "SANGWAN": "सांगवान", "MALIK": "मलिक", "DAHIYA": "दहिया", "HOODA": "हुड्डा", "HUDA": "हुड्डा",
    "DHANKHAR": "धनखड़", "KADIAN": "कादियान", "SHEORAN": "श्योराण", "GHANGHAS": "घणघस",
    "PHOGAT": "फोगाट", "RATHI": "राठी", "DALAL": "दलाल", "SEHRAWAT": "सहरावत", "GULIA": "गुलिया",
    "TANWAR": "तंवर", "CHAUHAN": "चौहान", "RATHORE": "राठौर", "RATHOR": "राठौर", "RATHAUR": "राठौर",
    "BHATI": "भाटी", "PANWAR": "पंवार", "PARMAR": "परमार", "TOMAR": "तोमर", "JAT": "जाट",
    "GUJAR": "गुर्जर", "GUJJAR": "गुज्जर", "GURJAR": "गुर्जर", "AHIR": "अहीर", "KUMHAR": "कुम्हार",
    "PRAJAPATI": "प्रजापति", "KHATI": "खाती", "LOHAR": "लोहार", "SUTHAR": "सुथार", "NAI": "नाई",
    "DHOBI": "धोबी", "BANIA": "बनिया", "BANIYA": "बनिया", "AGGARWAL": "अग्रवाल", "AGARWAL": "अग्रवाल",
    "GARG": "गर्ग", "GOYAL": "गोयल", "GUPTA": "गुप्ता", "BANSAL": "बंसल", "MITTAL": "मित्तल",
    "SINGLA": "सिंगला", "JINDAL": "जिंदल", "JAIN": "जैन", "SONI": "सोनी", "SUNAR": "सुनार", "MEHTA": "मेहता",
    "KHATRI": "खत्री", "ARORA": "अरोड़ा", "SETHI": "सेठी", "CHAWLA": "चावला", "NARULA": "नरूला",
    "THAKUR": "ठाकुर", "THAKER": "ठाकर", "THAKAR": "ठाकर", "BRAHMIN": "ब्राह्मण", "MEGHWAL": "मेघवाल",
    "VALMIKI": "वाल्मीकि", "KHAN": "खान", "MOHAMMAD": "मोहम्मद", "ALI": "अली", "SHEIKH": "शेख",
    "BERA": "बेरा", "MOGA": "मोगा", "GADA": "गाडा", "BABAL": "बाबल", "HARDU": "हरडू", "PUAN": "पुआण",
    "GHOTHAR": "घोठड़", "KHILERI": "खिलेरी", "MANJHU": "मांझू", "BAMAL": "बामल", "PANGHAL": "पंघाल",
    "BURDAK": "बुरड़क", "NEHRA": "नेहरा", "KULHARI": "कुल्हरी", "SUNDA": "सुंडा", "MUNDEL": "मुंडेल",
    "DAKA": "डाका", "JADIYA": "जाडिया", "DHOLIYA": "ढोलिया", "MENA": "मीणा", "MEENA": "मीणा", "MINA": "मीणा",
    # places in and around Hisar / Haryana
    "HISAR": "हिसार", "HISSAR": "हिसार", "ROHTAK": "रोहतक", "BHIWANI": "भिवानी", "SIRSA": "सिरसा",
    "FATEHABAD": "फतेहाबाद", "HANSI": "हांसी", "BARWALA": "बरवाला", "ADAMPUR": "आदमपुर",
    "AGROHA": "अग्रोहा", "UKLANA": "उकलाना", "NARNAUND": "नारनौंद", "JIND": "जींद", "TOHANA": "टोहाना",
    "BHATTU": "भट्टू", "SIWANI": "सिवानी", "TOSHAM": "तोशाम", "LOHARU": "लोहारू", "DABWALI": "डबवाली",
    "ELLENABAD": "ऐलनाबाद", "RATIA": "रतिया", "KAITHAL": "कैथल", "KARNAL": "करनाल", "PANIPAT": "पानीपत",
    "SONIPAT": "सोनीपत", "DELHI": "दिल्ली", "JAIPUR": "जयपुर", "RAJASTHAN": "राजस्थान", "PUNJAB": "पंजाब",
    "HARYANA": "हरियाणा", "BADSHAPUR": "बादशाहपुर", "MIRZAPUR": "मिर्ज़ापुर", "DHANSU": "धांसू",
    "GAON": "गांव", "VILLAGE": "गांव", "VPO": "गांव-डाक", "DHANI": "ढाणी", "MANDI": "मंडी",
    "COLONY": "कॉलोनी", "ROAD": "रोड", "CHOWK": "चौक", "NAGAR": "नगर", "PUR": "पुर", "PURA": "पुरा",
    # words seen in account details
    "HOME": "घर", "FARM": "खेत", "KHET": "खेत", "OLD": "पुराना", "NEW": "नया", "HISAB": "हिसाब",
    "HISSA": "हिस्सा", "KHETI": "खेती", "SON": "पुत्र", "FATHER": "पिता", "WIFE": "पत्नी",
    "BROTHER": "भाई", "CONTACT": "संपर्क", "CONTECT": "संपर्क", "CONTCT": "संपर्क", "MOBILE": "मोबाइल",
    "MOB": "मो.", "PH": "फ़ोन", "PHONE": "फ़ोन", "SO": "पुत्र", "WO": "पत्नी", "DO": "पुत्री",
    "TRADING": "ट्रेडिंग", "TRADERS": "ट्रेडर्स", "CO": "कं.", "COMPANY": "कंपनी", "AND": "और",
    "BEEJ": "बीज", "BHANDAR": "भंडार", "BHANDER": "भंडार", "STORE": "स्टोर", "SHOP": "दुकान",
    "TEST": "टेस्ट", "ONE": "वन", "CASH": "नकद", "BANK": "बैंक", "UPI": "यूपीआई",
}

ITEM_WORDS: dict[str, str] = {
    # companies and brands
    "BAYER": "बायर", "CORTEVA": "कॉर्टेवा", "ADAMA": "अदामा", "FMC": "एफएमसी", "UPL": "यूपीएल",
    "SYNGENTA": "सिंजेंटा", "DHANUKA": "धानुका", "COROMANDEL": "कोरोमंडल", "IFFCO": "इफको",
    "KRIBHCO": "कृभको", "NFL": "एनएफएल", "CHAMBAL": "चंबल", "TATA": "टाटा", "RALLIS": "रैलिस",
    "INSECTICIDES": "इंसेक्टिसाइड्स", "BASF": "बीएएसएफ", "SUMITOMO": "सुमितोमो", "PI": "पीआई",
    "GODREJ": "गोदरेज", "NAGARJUNA": "नागार्जुन", "SHIVALIK": "शिवालिक", "BESTAGRO": "बेस्ट एग्रो",
    "UTTAM": "उत्तम", "EXCEL": "एक्सेल", "MAHYCO": "माहिको", "NUZIVEEDU": "नुज़ीवीडू", "PIONEER": "पायनियर",
    "ADVANTA": "एडवांटा", "NATH": "नाथ", "KAVERI": "कावेरी", "RASI": "रासी", "ANKUR": "अंकुर",
    "HPM": "एचपीएम", "GHARDA": "घरडा", "CRYSTAL": "क्रिस्टल", "INDOFIL": "इंडोफिल", "BIOSTADT": "बायोस्टैड",
    # products seen in agri shops
    "CONFIDOR": "कॉन्फिडोर", "CORAGEN": "कोराजन", "ROUNDUP": "राउंडअप", "GRAMOXONE": "ग्रामोक्सोन",
    "GRAMOSONE": "ग्रामोक्सोन", "TRACER": "ट्रेसर", "DELEGATE": "डेलीगेट", "FERTERRA": "फर्टेरा",
    "HEXASTOP": "हेक्सास्टॉप", "HINDOL": "हिंडोल", "SAKED": "सकेड", "PANVEER": "पनवीर", "GUSTO": "गस्टो",
    "PARANEX": "पैरानेक्स", "TRAXX": "ट्रैक्स", "MERA": "मेरा", "CYPER": "साइपर", "CYPRA": "साइप्रा",
    "MONOCROWN": "मोनोक्राउन", "MACTARA": "मैकटारा", "MULTICUT": "मल्टीकट", "HULK": "हल्क",
    "ACEMAIN": "एसमेन", "AGRIWET": "एग्रीवेट", "CHLORGUARD": "क्लोरगार्ड", "ALL": "ऑल", "CLEAR": "क्लियर",
    "TOPIC": "टॉपिक", "AGIL": "एजिल", "SHAMIR": "शमीर", "MAC": "मैक", "GOLD": "गोल्ड", "PLUS": "प्लस",
    "SUPER": "सुपर", "ULTRA": "अल्ट्रा", "MAX": "मैक्स", "PRO": "प्रो", "STAR": "स्टार", "KING": "किंग",
    "POWER": "पावर", "TOTAL": "टोटल", "NEW": "न्यू", "MAIN": "मेन", "SE": "एसई", "EC": "ईसी", "SC": "एससी",
    "WP": "डब्ल्यूपी", "WG": "डब्ल्यूजी", "SL": "एसएल", "GR": "जीआर", "CS": "सीएस", "OD": "ओडी", "CR": "सीआर",
    # chemistry and fertiliser
    "UREA": "यूरिया", "DAP": "डीएपी", "NPK": "एनपीके", "MOP": "एमओपी", "SSP": "एसएसपी", "POTASH": "पोटाश",
    "ZINC": "जिंक", "SULPHUR": "सल्फर", "SULFUR": "सल्फर", "SULPHATE": "सल्फेट", "SULFATE": "सल्फेट",
    "BORON": "बोरॉन", "CALCIUM": "कैल्शियम", "NITRATE": "नाइट्रेट", "HUMIC": "ह्यूमिक", "ACID": "एसिड",
    "GYPSUM": "जिप्सम", "MAGNESIUM": "मैग्नीशियम", "AMMONIUM": "अमोनियम", "CHLORIDE": "क्लोराइड",
    "FERTILIZER": "खाद", "FERTILISER": "खाद", "KHAD": "खाद", "PESTICIDE": "कीटनाशक", "INSECTICIDE": "कीटनाशक",
    "HERBICIDE": "खरपतवारनाशक", "FUNGICIDE": "फफूंदनाशक", "WEEDICIDE": "खरपतवारनाशक", "SPRAY": "स्प्रे",
    "GRANULES": "दाने", "LIQUID": "लिक्विड", "POWDER": "पाउडर", "TONIC": "टॉनिक", "DAWAI": "दवाई",
    # crops and seed
    "SEED": "बीज", "SEEDS": "बीज", "BEEJ": "बीज", "WHEAT": "गेहूं", "GEHU": "गेहूं", "GEHUN": "गेहूं",
    "MUSTARD": "सरसों", "SARSON": "सरसों", "COTTON": "कपास", "KAPAS": "कपास", "NARMA": "नरमा",
    "PADDY": "धान", "DHAN": "धान", "RICE": "चावल", "BASMATI": "बासमती", "BAJRA": "बाजरा", "JOWAR": "ज्वार",
    "MAIZE": "मक्का", "MAKKA": "मक्का", "GUAR": "ग्वार", "GWAR": "ग्वार", "MOONG": "मूंग", "MUNG": "मूंग",
    "CHANA": "चना", "GRAM": "चना", "BARLEY": "जौ", "JAU": "जौ", "SUGARCANE": "गन्ना", "GANNA": "गन्ना",
    "TOBACCO": "तंबाकू", "TAMBAKU": "तंबाकू", "ONION": "प्याज", "POTATO": "आलू", "TOMATO": "टमाटर",
    "CHILLI": "मिर्च", "MIRCH": "मिर्च", "SOYABEAN": "सोयाबीन", "GROUNDNUT": "मूंगफली", "MOTH": "मोठ",
    "TIL": "तिल", "SESAME": "तिल", "CASTOR": "अरंडी", "BERSEEM": "बरसीम", "JAI": "जई", "OATS": "जई",
    "CROP": "फसल", "FASAL": "फसल", "HYBRID": "हाइब्रिड", "RCH": "आरसीएच", "BT": "बीटी",
    # money, packaging
    "CASH": "नकद", "BANK": "बैंक", "UPI": "यूपीआई", "BAG": "बैग", "BOTTLE": "बोतल", "PACKET": "पैकेट",
    "BOX": "बॉक्स", "DRUM": "ड्रम", "CAN": "कैन", "PACK": "पैक",
    "DESI": "देसी", "ATUL": "अतुल", "MAHADHAN": "महाधन", "MUSTERD": "मस्टर्ड", "PROTECT": "प्रोटेक्ट",
}

UNITS: dict[str, str] = {
    "G": "ग्राम", "GM": "ग्राम", "GMS": "ग्राम", "GRAM": "ग्राम", "KG": "किलो", "KGS": "किलो",
    "QTL": "क्विंटल", "ML": "एमएल", "L": "लीटर", "LT": "लीटर", "LTR": "लीटर", "LTRS": "लीटर",
    "PCS": "पीस", "PC": "पीस", "PKT": "पैकेट", "BTL": "बोतल", "INR": "₹", "RS": "रु.",
}

# name endings for compound names (longest first): AMARSINGH -> अमर + सिंह
SUFFIXES: list[str] = sorted(
    [
        "SINGH", "KUMAR", "PRAKASH", "PARKASH", "NIWAS", "NIVAS", "NARAYAN", "CHAND", "CHANDER", "KISHAN",
        "SWAROOP", "SARUP", "RAM", "LAL", "DAS", "PAL", "BIR", "VIR", "VEER", "NATH", "DEV", "DUTT",
        "BHAN", "PHAL", "DIN", "DEEN", "DAYAL", "RAJ", "JIT", "JEET", "PREET", "INDER", "ENDER",
        "WATI", "DEVI", "BAI", "MAL", "BALA", "PATI", "ANAND", "BHUSHAN",
    ],
    key=len,
    reverse=True,
)
NAME_WORDS.update(
    {
        "NARAYAN": "नारायण", "SWAROOP": "स्वरूप", "SARUP": "स्वरूप", "BIR": "बीर", "VIR": "वीर",
        "VEER": "वीर", "PHAL": "फल", "DIN": "दीन", "DEEN": "दीन", "DAYAL": "दयाल", "JIT": "जीत",
        "JEET": "जीत", "PREET": "प्रीत", "ENDER": "ेंद्र", "PATI": "पति", "BHUSHAN": "भूषण", "NIVAS": "निवास",
        "MAL": "मल", "NATH": "नाथ",
    }
)

LETTERS: dict[str, str] = {
    "A": "ए", "B": "बी", "C": "सी", "D": "डी", "E": "ई", "F": "एफ", "G": "जी", "H": "एच", "I": "आई",
    "J": "जे", "K": "के", "L": "एल", "M": "एम", "N": "एन", "O": "ओ", "P": "पी", "Q": "क्यू", "R": "आर",
    "S": "एस", "T": "टी", "U": "यू", "V": "वी", "W": "डब्ल्यू", "X": "एक्स", "Y": "वाई", "Z": "ज़ेड",
}
# fmt: on

_missing = [s for s in SUFFIXES if s not in NAME_WORDS]
assert not _missing, f"name endings without a Hindi form: {_missing}"
