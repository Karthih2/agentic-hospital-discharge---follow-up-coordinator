"""Step 1. Accept PDF or text, check the REAL content, reject bad input with a clear code.
Nothing is written to disk: the upload lives in memory only, so there is no file to delete afterwards."""
import io
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.core.config import settings

MESSAGES = {
    "EMPTY_INPUT": "No text was provided. Please paste the summary or enter your tasks manually.",
    "NOT_MEDICAL": "This does not look like a discharge summary. Please check the file or enter your tasks manually.",
    "UNREADABLE_PDF": "This PDF has no readable text (scanned images are not supported). "
                      "Please paste the text or enter your tasks manually.",
    "UNSUPPORTED_FILE": "Only PDF and plain text files are accepted.",
    "FILE_TOO_LARGE": "The file is too large.",
}
MEDICAL_WORDS = re.compile(r"\b(discharge|mg|ml|follow[- ]?up|advice|tab|tablet|capsule|appointment|medicine|"
                           r"review|test|dressing|doctor|hospital|patient|diagnosis|dose|daily|refer\w*)\b", re.I)
PDF_DANGER = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/AcroForm", b"/OpenAction", b"/RichMedia")
MIN_CHARS = 50
_pool = ThreadPoolExecutor(max_workers=2)


class InputError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(MESSAGES.get(code, code))


def _pdf_text(data: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if len(pdf.pages) > settings.max_pdf_pages:
            raise InputError("FILE_TOO_LARGE")
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def read_upload(data: bytes) -> tuple[str, str]:
    """Returns (text, source) where source is 'pdf' or 'text'."""
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise InputError("FILE_TOO_LARGE")
    if data[:5] == b"%PDF-":
        if any(tok in data for tok in PDF_DANGER):
            raise InputError("UNSUPPORTED_FILE")
        # ponytail: thread + timeout, not a separate OS process. Use a subprocess sandbox for hostile input at scale.
        try:
            text = _pool.submit(_pdf_text, data).result(timeout=20)
        except InputError:
            raise
        except (FutureTimeout, Exception):
            raise InputError("UNREADABLE_PDF")
        if not text.strip():
            raise InputError("UNREADABLE_PDF")
        return text, "pdf"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("UNSUPPORTED_FILE")
    if "\x00" in text:
        raise InputError("UNSUPPORTED_FILE")
    return text, "text"


def check_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        raise InputError("EMPTY_INPUT")
    if len(t) < MIN_CHARS or not MEDICAL_WORDS.search(t):
        raise InputError("NOT_MEDICAL")
    return t
