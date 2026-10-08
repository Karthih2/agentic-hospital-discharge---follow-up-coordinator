import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export const LANGS = [
  { code: "en", name: "English", native: "English" },
  { code: "ta", name: "Tamil", native: "தமிழ்" },
  { code: "hi", name: "Hindi", native: "हिन्दी" },
  { code: "te", name: "Telugu", native: "తెలుగు" },
  { code: "kn", name: "Kannada", native: "ಕನ್ನಡ" },
  { code: "ml", name: "Malayalam", native: "മലയാളം" },
] as const;
export type Lang = (typeof LANGS)[number]["code"];

type Row = Record<Lang, string>;
const t = (en: string, ta: string, hi: string, te: string, kn: string, ml: string): Row => ({ en, ta, hi, te, kn, ml });

// Short interface strings in all six languages. Longer landing copy stays English in this build.
export const STR = {
  navHow: t("How it works", "இது எப்படி செயல்படுகிறது", "यह कैसे काम करता है", "ఇది ఎలా పనిచేస్తుంది", "ಇದು ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ", "ഇത് എങ്ങനെ പ്രവർത്തിക്കുന്നു"),
  navSafety: t("Safety", "பாதுகாப்பு", "सुरक्षा", "భద్రత", "ಸುರಕ್ಷತೆ", "സുരക്ഷ"),
  navLanguages: t("Languages", "மொழிகள்", "भाषाएँ", "భాషలు", "ಭಾಷೆಗಳು", "ഭാഷകൾ"),
  navFamily: t("Family", "குடும்பம்", "परिवार", "కుటుంబం", "ಕುಟುಂಬ", "കുടുംബം"),
  navFaq: t("FAQ", "கேள்விகள்", "सामान्य प्रश्न", "ప్రశ్నలు", "ಪ್ರಶ್ನೆಗಳು", "ചോദ്യങ്ങൾ"),
  signIn: t("Sign in", "உள்நுழைக", "साइन इन", "సైన్ ఇన్", "ಸೈನ್ ಇನ್", "സൈൻ ഇൻ"),
  getStarted: t("Get started", "தொடங்குங்கள்", "शुरू करें", "ప్రారంభించండి", "ಪ್ರಾರಂಭಿಸಿ", "തുടങ്ങുക"),
  tryDemo: t("Try the demo", "டெமோவை முயற்சிக்கவும்", "डेमो आज़माएँ", "డెమో ప్రయత్నించండి", "ಡೆಮೊ ಪ್ರಯತ್ನಿಸಿ", "ഡെമോ പരീക്ഷിക്കുക"),
  heroTitle: t(
    "Your discharge papers, turned into a plan you can follow.",
    "உங்கள் டிஸ்சார்ஜ் ஆவணங்கள், நீங்கள் எளிதில் பின்பற்றக்கூடிய திட்டமாக.",
    "आपके डिस्चार्ज के कागज़ात, एक ऐसी योजना में जिसे आप आसानी से अपना सकें।",
    "మీ డిశ్చార్జ్ పత్రాలు, మీరు సులభంగా అనుసరించగల ప్రణాళికగా.",
    "ನಿಮ್ಮ ಡಿಸ್ಚಾರ್ಜ್ ದಾಖಲೆಗಳು, ನೀವು ಸುಲಭವಾಗಿ ಅನುಸರಿಸಬಹುದಾದ ಯೋಜನೆಯಾಗಿ.",
    "നിങ്ങളുടെ ഡിസ്ചാർജ് രേഖകൾ, നിങ്ങൾക്ക് എളുപ്പത്തിൽ പിന്തുടരാവുന്ന പദ്ധതിയായി.",
  ),
  heroSub: t(
    "Upload a discharge summary. Get tasks, dates, reminders and a timeline, explained in your language and tied to the exact line each one came from.",
    "டிஸ்சார்ஜ் சுருக்கத்தைப் பதிவேற்றுங்கள். பணிகள், தேதிகள், நினைவூட்டல்கள், காலவரிசை ஆகியவற்றை உங்கள் மொழியில், ஒவ்வொன்றும் எந்த வரியிலிருந்து வந்ததோ அதனுடன் இணைத்துப் பெறுங்கள்.",
    "डिस्चार्ज सारांश अपलोड करें। कार्य, तिथियाँ, रिमाइंडर और टाइमलाइन पाएँ, आपकी भाषा में समझाए गए और हर एक उसी पंक्ति से जुड़ा जहाँ से वह आया।",
    "డిశ్చార్జ్ సారాంశాన్ని అప్‌లోడ్ చేయండి. పనులు, తేదీలు, రిమైండర్లు, టైమ్‌లైన్ మీ భాషలో పొందండి, ప్రతిదీ అది వచ్చిన ఖచ్చితమైన వాక్యంతో అనుసంధానమై.",
    "ಡಿಸ್ಚಾರ್ಜ್ ಸಾರಾಂಶವನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ. ಕೆಲಸಗಳು, ದಿನಾಂಕಗಳು, ಜ್ಞಾಪನೆಗಳು ಮತ್ತು ಟೈಮ್‌ಲೈನ್ ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ ಪಡೆಯಿರಿ, ಪ್ರತಿಯೊಂದೂ ಬಂದ ನಿಖರ ಸಾಲಿಗೆ ಜೋಡಿಸಲಾಗಿದೆ.",
    "ഡിസ്ചാർജ് സംഗ്രഹം അപ്‌ലോഡ് ചെയ്യുക. ജോലികൾ, തീയതികൾ, ഓർമ്മപ്പെടുത്തലുകൾ, ടൈംലൈൻ എന്നിവ നിങ്ങളുടെ ഭാഷയിൽ നേടുക, ഓരോന്നും വന്ന കൃത്യമായ വരിയുമായി ബന്ധിപ്പിച്ച്.",
  ),
  entryFamily: t(
    "I am a patient or family member", "நான் நோயாளி அல்லது குடும்ப உறுப்பினர்", "मैं मरीज़ या परिवार का सदस्य हूँ",
    "నేను రోగిని లేదా కుటుంబ సభ్యుడిని", "ನಾನು ರೋಗಿ ಅಥವಾ ಕುಟುಂಬದ ಸದಸ್ಯ", "ഞാൻ രോഗിയോ കുടുംബാംഗമോ ആണ്"),
  entryDoctor: t(
    "I am a doctor", "நான் மருத்துவர்", "मैं डॉक्टर हूँ", "నేను వైద్యుడిని", "ನಾನು ವೈದ್ಯ", "ഞാൻ ഡോക്ടറാണ്"),
  logOut: t("Log out", "வெளியேறு", "लॉग आउट", "లాగ్ అవుట్", "ಲಾಗ್ ಔಟ್", "ലോഗ് ഔട്ട്"),
  hub: t("Family hub", "குடும்ப மையம்", "फैमिली हब", "కుటుంబ హబ్", "ಕುಟುಂಬ ಹಬ್", "ഫാമിലി ഹബ്"),
  notifications: t("Notifications", "அறிவிப்புகள்", "सूचनाएँ", "నోటిఫికేషన్లు", "ಅಧಿಸೂಚನೆಗಳು", "അറിയിപ്പുകൾ"),
  members: t("Members and consent", "உறுப்பினர்கள், ஒப்புதல்", "सदस्य और सहमति", "సభ్యులు, అనుమతి", "ಸದಸ್ಯರು ಮತ್ತು ಒಪ್ಪಿಗೆ", "അംഗങ്ങളും സമ്മതവും"),
  disclaimer: t(
    "This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear.",
    "இந்தக் கருவி உங்கள் டிஸ்சார்ஜ் அறிவுரைகளை ஒழுங்கமைக்கிறது. இது மருத்துவ ஆலோசனை வழங்காது. தெளிவற்ற எதையும் உங்கள் மருத்துவரிடம் கேளுங்கள்.",
    "यह टूल आपके डिस्चार्ज निर्देशों को व्यवस्थित करता है। यह चिकित्सा सलाह नहीं देता। जो भी अस्पष्ट हो उसके बारे में अपने डॉक्टर से पूछें।",
    "ఈ సాధనం మీ డిశ్చార్జ్ సూచనలను క్రమబద్ధీకరిస్తుంది. ఇది వైద్య సలహా ఇవ్వదు. అస్పష్టమైన ఏదైనా మీ వైద్యుడిని అడగండి.",
    "ಈ ಸಾಧನ ನಿಮ್ಮ ಡಿಸ್ಚಾರ್ಜ್ ಸೂಚನೆಗಳನ್ನು ಸಂಘಟಿಸುತ್ತದೆ. ಇದು ವೈದ್ಯಕೀಯ ಸಲಹೆ ನೀಡುವುದಿಲ್ಲ. ಅಸ್ಪಷ್ಟವಾದ ಯಾವುದನ್ನಾದರೂ ನಿಮ್ಮ ವೈದ್ಯರನ್ನು ಕೇಳಿ.",
    "ഈ ഉപകരണം നിങ്ങളുടെ ഡിസ്ചാർജ് നിർദ്ദേശങ്ങൾ ക്രമീകരിക്കുന്നു. ഇത് വൈദ്യോപദേശം നൽകുന്നില്ല. വ്യക്തമല്ലാത്ത എന്തിനെക്കുറിച്ചും നിങ്ങളുടെ ഡോക്ടറോട് ചോദിക്കുക.",
  ),
} satisfies Record<string, Row>;

type Ctx = { lang: Lang; setLang: (l: Lang) => void; s: (k: keyof typeof STR) => string };
const I18n = createContext<Ctx>(null!);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    try {
      const v = localStorage.getItem("lang") as Lang | null;
      return v && LANGS.some((l) => l.code === v) ? v : "en";
    } catch {
      return "en";
    }
  });
  useEffect(() => {
    document.documentElement.lang = lang;
    try { localStorage.setItem("lang", lang); } catch { /* storage can be blocked */ }
  }, [lang]);
  const value = useMemo<Ctx>(() => ({ lang, setLang, s: (k) => STR[k][lang] }), [lang]);
  return <I18n.Provider value={value}>{children}</I18n.Provider>;
}
export const useI18n = () => useContext(I18n);
