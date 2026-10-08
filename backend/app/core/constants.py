DISCLAIMER = ("This tool organizes your discharge instructions. It does not give medical advice. "
              "Ask your doctor about anything unclear.")
PROVIDER_LABEL = "Suggestion only, not a guarantee of availability or suitability"
WAITING = "Waiting for doctor review"

ROLES = ("patient", "family", "doctor", "admin")
LANGS = ("en", "ta", "hi", "te", "kn", "ml")
TRANSLATE_LANGS = ("ta", "hi", "te", "kn", "ml")  # every task is translated into all of these
REQUIRED_LANGS = ("ta", "hi")  # demo-polished: a rewrite without these is rejected. te/kn/ml are dropped if they fail checks
LANG_NAMES = {"en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam"}
TYPES = ("appointment", "test", "referral", "medicine", "care_instruction", "date", "warning_sign")
STATUSES = ("Pending", "Completed", "Needs Review")
ACCESS_LEVELS = ("full", "appointments", "reminders")
HUB_ROLES = ("manager", "patient", "viewer")
SCHEMA_VERSION = 2
APPT_TYPES = ("appointment", "test", "referral")

REASON_TEXT = {
    "MISSING_DATE": "Date is missing",
    "MISSING_DOSE": "Dose is not mentioned",
    "MISSING_TIMING": "Timing is not mentioned",
    "MISSING_DURATION": "Duration is not mentioned",
    "MISSING_DOCTOR": "Doctor or specialty is missing",
    "AMBIGUOUS_DATE": "Date or duration is unclear",
    "SYMPTOM_QUESTION": "Contains a symptom question",
    "MEDICINE_CHANGE": "Mentions a medicine change or stop order",
    "MEDICINE_CONFLICT": "Two instructions for this medicine differ",
    "LOW_CONFIDENCE": "Reading confidence is low",
    "UNCATEGORISED": "Could not be classified",
    "SOURCE_NOT_FOUND": "Source line not found in the summary",
    "USER_FLAGGED": "Flagged for review by the patient or family",
    "EXTRACTION_FAILED": "The summary could not be read",
    "MANUAL_ENTRY": "Entered by hand, a doctor must confirm it",
}

# Fixed medicine card labels. Order matches MEDICINE_KEYS.
MEDICINE_LABELS = {
    "en": ["Medicine name", "Dose", "Route", "Timing", "Duration", "Special instructions"],
    "ta": ["மருந்தின் பெயர்", "அளவு", "எப்படி எடுப்பது", "நேரம்", "காலம்", "சிறப்பு வழிமுறைகள்"],
    "hi": ["दवा का नाम", "खुराक", "कैसे लेना है", "समय", "अवधि", "विशेष निर्देश"],
    "te": ["మందు పేరు", "మోతాదు", "ఎలా తీసుకోవాలి", "సమయం", "వ్యవధి", "ప్రత్యేక సూచనలు"],
    "kn": ["ಔಷಧದ ಹೆಸರು", "ಡೋಸ್", "ಹೇಗೆ ತೆಗೆದುಕೊಳ್ಳಬೇಕು", "ಸಮಯ", "ಅವಧಿ", "ವಿಶೇಷ ಸೂಚನೆಗಳು"],
    "ml": ["മരുന്നിന്റെ പേര്", "ഡോസ്", "എങ്ങനെ കഴിക്കണം", "സമയം", "കാലയളവ്", "പ്രത്യേക നിർദ്ദേശങ്ങൾ"],
}
MEDICINE_KEYS = ["name", "dose", "route", "timing", "duration", "special"]

# Notification text comes only from these templates. No clinical text.
TEMPLATES = {
    "reminder_due_today": {
        "en": "You have a task due today. Open the app to view it.",
        "ta": "இன்று உங்களுக்கு ஒரு பணி உள்ளது. பார்க்க ஆப்பைத் திறக்கவும்.",
        "hi": "आज आपका एक कार्य है। देखने के लिए ऐप खोलें।"},
    "reminder_due_tomorrow": {
        "en": "You have a task due tomorrow. Open the app to view it.",
        "ta": "நாளை உங்களுக்கு ஒரு பணி உள்ளது. பார்க்க ஆப்பைத் திறக்கவும்.",
        "hi": "कल आपका एक कार्य है। देखने के लिए ऐप खोलें।"},
    "missed_task": {
        "en": "A task was not completed by its due date. Open the app to view it.",
        "ta": "ஒரு பணி குறித்த தேதிக்குள் முடிக்கப்படவில்லை. பார்க்க ஆப்பைத் திறக்கவும்.",
        "hi": "एक कार्य निर्धारित तिथि तक पूरा नहीं हुआ। देखने के लिए ऐप खोलें।"},
    "review_waiting": {
        "en": "An item is waiting for doctor review.",
        "ta": "ஒரு உருப்படி மருத்துவர் மதிப்பாய்வுக்காக காத்திருக்கிறது.",
        "hi": "एक आइटम डॉक्टर की समीक्षा की प्रतीक्षा में है।"},
    "review_resolved": {
        "en": "An item was reviewed by your doctor.",
        "ta": "ஒரு உருப்படி உங்கள் மருத்துவரால் மதிப்பாய்வு செய்யப்பட்டது.",
        "hi": "एक आइटम की आपके डॉक्टर ने समीक्षा की।"},
    "hub_invite": {
        "en": "You have a new family hub invitation. Open the app to answer it.",
        "ta": "புதிய குடும்ப மையம் அழைப்பு உள்ளது. பதிலளிக்க ஆப்பைத் திறக்கவும்.",
        "hi": "आपको एक नया फैमिली हब निमंत्रण मिला है। जवाब देने के लिए ऐप खोलें।"},
    "callback_requested": {
        "en": "Your callback request was received. The hospital will call you. Your number stays private.",
        "ta": "உங்கள் அழைப்பு கோரிக்கை பெறப்பட்டது. மருத்துவமனை உங்களை அழைக்கும். உங்கள் எண் தனிப்பட்டதாக இருக்கும்.",
        "hi": "आपका कॉलबैक अनुरोध मिल गया। अस्पताल आपको कॉल करेगा। आपका नंबर निजी रहेगा।"},
    "callback_completed": {
        "en": "Your callback is complete.",
        "ta": "உங்கள் அழைப்பு முடிந்தது.",
        "hi": "आपका कॉलबैक पूरा हुआ।"},
}


_MORE = {
    "hub_invite": {
        "te": "మీకు కొత్త కుటుంబ హబ్ ఆహ్వానం ఉంది. సమాధానం ఇవ్వడానికి యాప్ తెరవండి.",
        "kn": "ನಿಮಗೆ ಹೊಸ ಕುಟುಂಬ ಹಬ್ ಆಹ್ವಾನ ಇದೆ. ಉತ್ತರಿಸಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
        "ml": "നിങ്ങൾക്ക് ഒരു പുതിയ ഫാമിലി ഹബ് ക്ഷണം ഉണ്ട്. മറുപടി നൽകാൻ ആപ്പ് തുറക്കുക."},
    "reminder_due_today": {
        "te": "ఈ రోజు మీకు ఒక పని ఉంది. చూడటానికి యాప్ తెరవండి.",
        "kn": "ಇಂದು ನಿಮಗೆ ಒಂದು ಕೆಲಸ ಇದೆ. ನೋಡಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
        "ml": "ഇന്ന് നിങ്ങൾക്ക് ഒരു ജോലി ഉണ്ട്. കാണാൻ ആപ്പ് തുറക്കുക."},
    "reminder_due_tomorrow": {
        "te": "రేపు మీకు ఒక పని ఉంది. చూడటానికి యాప్ తెరవండి.",
        "kn": "ನಾಳೆ ನಿಮಗೆ ಒಂದು ಕೆಲಸ ಇದೆ. ನೋಡಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
        "ml": "നാളെ നിങ്ങൾക്ക് ഒരു ജോലി ഉണ്ട്. കാണാൻ ആപ്പ് തുറക്കുക."},
    "missed_task": {
        "te": "ఒక పని గడువు తేదీలోగా పూర్తి కాలేదు. చూడటానికి యాప్ తెరవండి.",
        "kn": "ಒಂದು ಕೆಲಸ ನಿಗದಿತ ದಿನಾಂಕದೊಳಗೆ ಪೂರ್ಣಗೊಂಡಿಲ್ಲ. ನೋಡಲು ಆ್ಯಪ್ ತೆರೆಯಿರಿ.",
        "ml": "ഒരു ജോലി നിശ്ചിത തീയതിക്കുള്ളിൽ പൂർത്തിയായിട്ടില്ല. കാണാൻ ആപ്പ് തുറക്കുക."},
    "review_waiting": {
        "te": "ఒక అంశం వైద్యుని సమీక్ష కోసం వేచి ఉంది.",
        "kn": "ಒಂದು ಅಂಶ ವೈದ್ಯರ ಪರಿಶೀಲನೆಗಾಗಿ ಕಾಯುತ್ತಿದೆ.",
        "ml": "ഒരു ഇനം ഡോക്ടറുടെ അവലോകനത്തിനായി കാത്തിരിക്കുന്നു."},
    "review_resolved": {
        "te": "ఒక అంశాన్ని మీ వైద్యుడు సమీక్షించారు.",
        "kn": "ಒಂದು ಅಂಶವನ್ನು ನಿಮ್ಮ ವೈದ್ಯರು ಪರಿಶೀಲಿಸಿದ್ದಾರೆ.",
        "ml": "ഒരു ഇനം നിങ്ങളുടെ ഡോക്ടർ അവലോകനം ചെയ്തു."},
    "callback_requested": {
        "te": "మీ కాల్‌బ్యాక్ అభ్యర్థన అందింది. ఆసుపత్రి మీకు కాల్ చేస్తుంది. మీ నంబర్ ప్రైవేట్‌గా ఉంటుంది.",
        "kn": "ನಿಮ್ಮ ಕಾಲ್‌ಬ್ಯಾಕ್ ವಿನಂತಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ಆಸ್ಪತ್ರೆ ನಿಮಗೆ ಕರೆ ಮಾಡುತ್ತದೆ. ನಿಮ್ಮ ಸಂಖ್ಯೆ ಖಾಸಗಿಯಾಗಿರುತ್ತದೆ.",
        "ml": "നിങ്ങളുടെ കോൾബാക്ക് അഭ്യർത്ഥന ലഭിച്ചു. ആശുപത്രി നിങ്ങളെ വിളിക്കും. നിങ്ങളുടെ നമ്പർ സ്വകാര്യമായിരിക്കും."},
    "callback_completed": {
        "te": "మీ కాల్‌బ్యాక్ పూర్తయింది.",
        "kn": "ನಿಮ್ಮ ಕಾಲ್‌ಬ್ಯಾಕ್ ಪೂರ್ಣಗೊಂಡಿದೆ.",
        "ml": "നിങ്ങളുടെ കോൾബാക്ക് പൂർത്തിയായി."},
}
for _k, _v in _MORE.items():
    TEMPLATES[_k].update(_v)
