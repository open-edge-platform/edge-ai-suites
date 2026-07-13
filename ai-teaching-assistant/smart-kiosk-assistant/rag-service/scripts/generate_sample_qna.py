"""Generate one Q&A JSONL per sample knowledge-base doc.

Output schema matches knowledge-base/store_qna.jsonl:
    {"question": "...", "answer": "...", "nature": "direct_fact" | "spanning"}

Usage
-----
    python scripts/generate_sample_qna.py
    # writes:
    #   knowledge-base-samples/MegaRetail-M.qna.jsonl
    #   knowledge-base-samples/QuickBite-M.qna.jsonl
    #   knowledge-base-samples/SkyJet-S.qna.jsonl
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT.parent / "knowledge-base-samples"

RETAIL_BRAND = "MegaRetail Hypermart"
QSR_BRAND = "QuickBite Express"
AIRLINE_BRAND = "SkyJet Airways"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _emit(out: list[dict], q: str, a: str, nature: str) -> None:
    out.append({"question": q.strip(), "answer": a.strip(), "nature": nature})


def _parse_top_metadata(text: str) -> dict[str, str]:
    """Return {label: value} from the leading `- **Label**: value` block."""
    meta: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        # Multiple `Label: value | Label: value` per line are common
        # Split on " | " then per `**Label**: value`
        parts = re.split(r"\s+\|\s+", line[2:])
        for part in parts:
            m = re.match(r"\*\*([^*]+)\*\*\s*:\s*(.+?)\s*$", part)
            if m:
                meta[m.group(1).strip()] = m.group(2).strip()
    return meta


def _strip_md(s: str) -> str:
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", s).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Retail (MegaRetail Hypermart)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Aisle:
    number: int
    name: str
    location: str = ""
    temp: str = ""
    restocking: str = ""
    staff: str = ""
    note: str = ""


def generate_retail_qna(text: str) -> list[dict]:
    out: list[dict] = []
    lines = text.splitlines()

    # ── Header / global facts ─────────────────────────────────────────────
    header_block = []
    for ln in lines:
        if ln.startswith("## "):
            break
        header_block.append(ln)
    meta = _parse_top_metadata("\n".join(header_block))

    if "Store Name" in meta:
        _emit(out, f"What is the store name?", f"The store name is {meta['Store Name']}.", "direct_fact")
    if "Tagline" in meta:
        _emit(out, f"What is the tagline of {RETAIL_BRAND}?",
              f"The tagline of {RETAIL_BRAND} is {meta['Tagline']}.", "direct_fact")
    if "Store Type" in meta:
        _emit(out, f"What type of store is {RETAIL_BRAND}?",
              f"{RETAIL_BRAND} is a {meta['Store Type']}.", "direct_fact")
    if "Parent Company" in meta:
        _emit(out, f"Who owns {RETAIL_BRAND}?",
              f"{RETAIL_BRAND} is owned by {meta['Parent Company']}.", "direct_fact")
    if "GST Registration" in meta:
        _emit(out, f"What is the GST registration number of {RETAIL_BRAND}?",
              f"The GST registration number of {RETAIL_BRAND} is {meta['GST Registration']}.", "direct_fact")
    if "FSSAI License" in meta:
        _emit(out, f"What is the FSSAI license number of {RETAIL_BRAND}?",
              f"The FSSAI license number is {meta['FSSAI License']}.", "direct_fact")
    if "Hours" in meta:
        _emit(out, f"What are the operating hours of {RETAIL_BRAND}?",
              f"{RETAIL_BRAND} operates {meta['Hours']}.", "direct_fact")
    if "Peak Hours" in meta:
        _emit(out, f"When are the peak hours at {RETAIL_BRAND}?",
              f"Peak hours at {RETAIL_BRAND} are {meta['Peak Hours']}.", "direct_fact")
    if "Off-Peak (Recommended)" in meta:
        _emit(out, f"When is the best off-peak time to visit {RETAIL_BRAND}?",
              f"The recommended off-peak time is {meta['Off-Peak (Recommended)']}.", "direct_fact")
    if "Main Entrance" in meta:
        _emit(out, f"Where is the main entrance of {RETAIL_BRAND}?",
              f"The main entrance is the {meta['Main Entrance']}.", "direct_fact")
    if "Secondary Entrance" in meta:
        _emit(out, f"Where is the secondary entrance of {RETAIL_BRAND}?",
              f"The secondary entrance is the {meta['Secondary Entrance']}.", "direct_fact")
    if "Loyalty Program" in meta:
        _emit(out, f"What is the loyalty program at {RETAIL_BRAND}?",
              f"The loyalty program is {meta['Loyalty Program']}.", "direct_fact")
    if "Customer Service Desk" in meta:
        _emit(out, f"Where is the customer service desk in {RETAIL_BRAND}?",
              f"The customer service desk is {meta['Customer Service Desk']}.", "direct_fact")
    if "ATMs" in meta:
        _emit(out, f"Where are the ATMs in {RETAIL_BRAND}?",
              f"ATMs: {meta['ATMs']}.", "direct_fact")
    if "Free Wi-Fi" in meta:
        _emit(out, f"Is there free Wi-Fi at {RETAIL_BRAND}?",
              f"Yes, free Wi-Fi is available: {meta['Free Wi-Fi']}.", "direct_fact")
    if "Restrooms & First Aid" in meta:
        _emit(out, f"Where are the restrooms and first aid in {RETAIL_BRAND}?",
              f"Restrooms and first aid are {meta['Restrooms & First Aid']}.", "direct_fact")
    if "Lost & Found" in meta:
        _emit(out, f"Where is lost and found at {RETAIL_BRAND}?",
              f"Lost and found is at the {meta['Lost & Found']}.", "direct_fact")

    # ── Tag system ────────────────────────────────────────────────────────
    in_tag_section = False
    for ln in lines:
        if ln.startswith("## Tag System"):
            in_tag_section = True
            continue
        if in_tag_section and ln.startswith("## "):
            break
        if in_tag_section and ln.startswith("- "):
            for tag_def in re.split(r"\s+\|\s+", ln[2:]):
                m = re.match(r"\*\*([A-Z]+)\*\*\s*:\s*(.+)$", tag_def)
                if m:
                    color, meaning = m.group(1), m.group(2).strip()
                    _emit(out, f"What does the {color} tag mean at {RETAIL_BRAND}?",
                          f"At {RETAIL_BRAND}, the {color} tag indicates: {meaning}.",
                          "direct_fact")

    # ── Aisle parsing ─────────────────────────────────────────────────────
    aisle_re = re.compile(r"^## AISLE\s+(\d+):\s*(.+?)\s*$")
    subsec_re = re.compile(r"^###\s+(.+?)\s*$")
    bullet_re = re.compile(r"^- \*\*([^*]+)\*\*\s*(.*)$")

    current: Aisle | None = None
    current_sub: str | None = None
    seen_aisle_header = False

    for ln in lines:
        m = aisle_re.match(ln)
        if m:
            current = Aisle(number=int(m.group(1)), name=m.group(2).strip())
            current_sub = None
            seen_aisle_header = True
            continue
        if current is None:
            continue
        if ln.startswith("## "):
            current = None
            continue
        sm = subsec_re.match(ln)
        if sm:
            current_sub = sm.group(1).strip()
            continue
        bm = bullet_re.match(ln)
        if not bm:
            continue
        name, rest = bm.group(1).strip(), bm.group(2).strip()
        # Aisle metadata bullets (before first ### subsection)
        if current_sub is None:
            value = rest.lstrip(": ").strip()
            label = name
            if label == "Location":
                current.location = value
                _emit(out,
                      f"Where is Aisle {current.number} ({current.name}) located in {RETAIL_BRAND}?",
                      f"Aisle {current.number} ({current.name}) is located at {value}.",
                      "direct_fact")
            elif label == "Temperature Zone":
                current.temp = value
                _emit(out,
                      f"What is the temperature zone of Aisle {current.number} ({current.name}) in {RETAIL_BRAND}?",
                      f"Aisle {current.number} ({current.name}) temperature zone: {value}.",
                      "direct_fact")
            elif label == "Restocking":
                current.restocking = value
                _emit(out,
                      f"When is restocking done in Aisle {current.number} ({current.name}) at {RETAIL_BRAND}?",
                      f"Restocking in Aisle {current.number} ({current.name}): {value}.",
                      "direct_fact")
            elif label == "Staff":
                current.staff = value
                _emit(out,
                      f"How many staff are assigned to Aisle {current.number} ({current.name}) at {RETAIL_BRAND}?",
                      f"Staffing in Aisle {current.number} ({current.name}): {value}.",
                      "direct_fact")
            elif label in {"Waste Policy", "Note", "In-Store Bakery Open"}:
                current.note = value
                _emit(out,
                      f"What is the {label.lower()} for Aisle {current.number} ({current.name}) at {RETAIL_BRAND}?",
                      f"{label} for Aisle {current.number} ({current.name}): {value}.",
                      "direct_fact")
            continue

        # Product bullet
        product = name
        # Pull out tags
        tag_match = re.search(r"\bTags?\s*:\s*([^|]+?)(?:\s*\||$)", rest)
        tags = tag_match.group(1).strip() if tag_match else ""
        details = re.sub(r"\bTags?\s*:.*$", "", rest).strip(" -\u2014|")
        details = details.strip(" -\u2014|").strip()
        location_str = current.location or f"Aisle {current.number} ({current.name})"

        # Where can I find <product>
        loc_answer = (
            f"{product} is in Aisle {current.number}: {current.name.upper()} "
            f"({location_str}) | Section: {current_sub}."
        )
        if details:
            loc_answer += f" Details: {details}."
        if tags:
            loc_answer += f" Tags: {tags}."
        _emit(out,
              f"Where can I find {product} in {RETAIL_BRAND}?",
              loc_answer,
              "spanning")

        # What aisle / which section
        _emit(out,
              f"Which aisle has {product} at {RETAIL_BRAND}?",
              f"{product} is in Aisle {current.number}: {current.name}, section {current_sub}.",
              "direct_fact")

        # Tags
        if tags:
            _emit(out,
                  f"What tags does {product} have at {RETAIL_BRAND}?",
                  f"{product} is tagged: {tags}.",
                  "direct_fact")

        # Pack / size details
        if details:
            _emit(out,
                  f"What pack sizes are available for {product} at {RETAIL_BRAND}?",
                  f"{product} is available as: {details}.",
                  "direct_fact")

    if not seen_aisle_header:
        # Fallback: nothing parsed
        pass

    return out


# ─────────────────────────────────────────────────────────────────────────────
# QSR (QuickBite Express)
# ─────────────────────────────────────────────────────────────────────────────

DIET_TAG_LABELS = {
    "V": "pure vegetarian",
    "E": "eggetarian (contains egg)",
    "NV": "non-vegetarian",
    "VE": "vegan",
    "J": "Jain (no onion, no garlic)",
    "GF": "gluten-free option available",
    "S": "spicy",
    "SS": "extra spicy",
    "M": "mild",
    "NEW": "a new item",
    "HIT": "a bestseller",
    "LD": "limited daily quantity",
}


def _qsr_tags(rest: str) -> list[str]:
    return re.findall(r"\[([A-Z]+)\]", rest)


def _qsr_describe_tags(tags: list[str]) -> str:
    if not tags:
        return ""
    pieces = [DIET_TAG_LABELS.get(t, t) for t in tags]
    return ", ".join(pieces)


def generate_qsr_qna(text: str) -> list[dict]:
    out: list[dict] = []
    lines = text.splitlines()

    # Header
    header_block = []
    for ln in lines:
        if ln.startswith("## "):
            break
        header_block.append(ln)
    meta = _parse_top_metadata("\n".join(header_block))

    label_to_question = {
        "Brand Name": ("What is the brand name of this outlet?", "The brand name is {v}."),
        "Tagline": (f"What is the tagline of {QSR_BRAND}?", f"The tagline of {QSR_BRAND} is " + "{v}."),
        "Outlet Type": (f"What type of outlet is {QSR_BRAND}?", f"{QSR_BRAND} is a " + "{v}."),
        "Parent Company": (f"Who owns {QSR_BRAND}?", f"{QSR_BRAND} is owned by " + "{v}."),
        "Cuisine": (f"What cuisine does {QSR_BRAND} serve?", f"{QSR_BRAND} serves " + "{v}."),
        "FSSAI License": (f"What is the FSSAI license of {QSR_BRAND}?", "The FSSAI license is {v}."),
        "GST Registration": (f"What is the GST registration of {QSR_BRAND}?", "The GST registration is {v}."),
        "Hours": (f"What are the operating hours of {QSR_BRAND}?", f"{QSR_BRAND} hours: " + "{v}."),
        "Breakfast Hours": (f"What are the breakfast hours at {QSR_BRAND}?", "Breakfast is served {v}."),
        "All-Day Menu": (f"When is the all-day menu available at {QSR_BRAND}?", "All-day menu: {v}."),
        "Last Order": (f"When is last order at {QSR_BRAND}?", "Last order is {v}."),
        "Kitchen Closes": (f"When does the kitchen close at {QSR_BRAND}?", "Kitchen closes {v}."),
        "Seating Capacity": (f"What is the seating capacity at {QSR_BRAND}?", "Seating capacity: {v}."),
        "Delivery": (f"Does {QSR_BRAND} offer delivery?", "Delivery: {v}."),
        "Takeaway": (f"Does {QSR_BRAND} offer takeaway?", "Takeaway: {v}."),
        "Dine-In": (f"Does {QSR_BRAND} offer dine-in?", "Dine-in: {v}."),
        "Parking": (f"Is parking available at {QSR_BRAND}?", "Parking: {v}."),
        "Wi-Fi": (f"Is Wi-Fi available at {QSR_BRAND}?", "Wi-Fi: {v}."),
        "Loyalty Program": (f"What is the loyalty program at {QSR_BRAND}?", "Loyalty program: {v}."),
        "Catering / Bulk Orders": (f"Does {QSR_BRAND} take catering or bulk orders?", "Catering: {v}."),
    }
    for label, (q, a_tpl) in label_to_question.items():
        if label in meta:
            _emit(out, q, a_tpl.format(v=meta[label]), "direct_fact")

    # Dietary tag system
    in_tags = False
    for ln in lines:
        if ln.startswith("## Dietary Tag System"):
            in_tags = True
            continue
        if in_tags and ln.startswith("## "):
            break
        if in_tags and ln.startswith("- **"):
            m = re.match(r"-\s+\*\*\[([A-Z]+)\]\*\*\s*:\s*(.+)$", ln)
            if m:
                code, meaning = m.group(1), m.group(2).strip()
                _emit(out, f"What does the {code} tag mean at {QSR_BRAND}?",
                      f"At {QSR_BRAND}, [{code}] means: {meaning}.", "direct_fact")

    # Menus
    menu_re = re.compile(r"^## MENU\s+(\d+):\s*(.+?)\s*$")
    subsec_re = re.compile(r"^###\s+(.+?)\s*$")
    item_re = re.compile(r"^- \*\*([^*]+)\*\*\s*\u2014\s*(.+)$")
    price_re = re.compile(r"\u20b9\s*([\d,]+)")
    multi_price_re = re.compile(
        r"(Personal|Regular|Large|Small|Medium)\s*\u20b9\s*([\d,]+)", re.IGNORECASE
    )

    current_menu: tuple[int, str] | None = None
    current_sub: str | None = None

    for ln in lines:
        mm = menu_re.match(ln)
        if mm:
            current_menu = (int(mm.group(1)), mm.group(2).strip())
            current_sub = None
            continue
        if current_menu is None:
            continue
        if ln.startswith("## "):
            current_menu = None
            continue
        sm = subsec_re.match(ln)
        if sm:
            current_sub = sm.group(1).strip()
            continue
        im = item_re.match(ln)
        if not im:
            continue
        dish, rest = im.group(1).strip(), im.group(2).strip()
        menu_num, menu_name = current_menu
        sub = current_sub or menu_name

        tags = _qsr_tags(rest)
        tag_desc = _qsr_describe_tags(tags)

        # Pricing
        multi = multi_price_re.findall(rest)
        single_prices = price_re.findall(rest)
        if multi:
            price_str = "; ".join(f"{tier} \u20b9{price}" for tier, price in multi)
            _emit(out,
                  f"How much does {dish} cost at {QSR_BRAND}?",
                  f"{dish} is priced at: {price_str}.",
                  "direct_fact")
        elif single_prices:
            _emit(out,
                  f"How much does {dish} cost at {QSR_BRAND}?",
                  f"{dish} costs \u20b9{single_prices[0]} at {QSR_BRAND}.",
                  "direct_fact")

        # What is it / description
        # Description = part after the price block and before the tags
        desc = rest
        desc = re.sub(r"\[[A-Z]+\]", "", desc).strip(" |")
        # Strip leading price numbers
        desc = re.sub(r"^[\u20b9\d/,\s\-Personal\u2014RegulargrLarSmlMediu]+\|", "", desc).strip()
        desc = desc.strip(" |\u2014")
        if desc:
            _emit(out,
                  f"What is {dish} at {QSR_BRAND}?",
                  f"{dish} (Menu {menu_num}: {menu_name}, {sub}) — {desc}." +
                  (f" Dietary: {tag_desc}." if tag_desc else ""),
                  "spanning")

        # Which menu it's on
        _emit(out,
              f"Which menu is {dish} on at {QSR_BRAND}?",
              f"{dish} is on Menu {menu_num}: {menu_name}, section {sub}.",
              "direct_fact")

        # Dietary
        if tags:
            if "V" in tags:
                _emit(out, f"Is {dish} vegetarian at {QSR_BRAND}?",
                      f"Yes, {dish} is pure vegetarian [V].", "direct_fact")
            if "VE" in tags:
                _emit(out, f"Is {dish} vegan at {QSR_BRAND}?",
                      f"Yes, {dish} is vegan [VE].", "direct_fact")
            if "NV" in tags:
                _emit(out, f"Is {dish} non-vegetarian at {QSR_BRAND}?",
                      f"Yes, {dish} is non-vegetarian [NV].", "direct_fact")
            if "J" in tags:
                _emit(out, f"Is {dish} Jain-friendly at {QSR_BRAND}?",
                      f"Yes, {dish} is Jain-friendly (no onion, no garlic) [J].",
                      "direct_fact")
            if "GF" in tags:
                _emit(out, f"Is {dish} gluten-free at {QSR_BRAND}?",
                      f"Yes, a gluten-free option is available for {dish} [GF].",
                      "direct_fact")
            if "S" in tags or "SS" in tags:
                level = "extra spicy" if "SS" in tags else "spicy"
                _emit(out, f"Is {dish} spicy at {QSR_BRAND}?",
                      f"Yes, {dish} is {level}.", "direct_fact")
            if "HIT" in tags:
                _emit(out, f"Is {dish} a bestseller at {QSR_BRAND}?",
                      f"Yes, {dish} is marked as a bestseller [HIT].",
                      "direct_fact")
            if "NEW" in tags:
                _emit(out, f"Is {dish} a new item at {QSR_BRAND}?",
                      f"Yes, {dish} is a new item [NEW].", "direct_fact")
            if "LD" in tags:
                _emit(out, f"Is {dish} limited in daily quantity at {QSR_BRAND}?",
                      f"Yes, {dish} is limited daily quantity [LD].", "direct_fact")

    # Menu-level metadata (serving hours, base options)
    menu_re2 = re.compile(r"^## MENU\s+(\d+):\s*(.+?)\s*$")
    current_menu = None
    captured_meta_for: set[tuple[int, str]] = set()
    for ln in lines:
        mm = menu_re2.match(ln)
        if mm:
            current_menu = (int(mm.group(1)), mm.group(2).strip())
            continue
        if current_menu is None or ln.startswith("## ") or ln.startswith("### "):
            if ln.startswith("## "):
                current_menu = None
            continue
        if ln.startswith("- **") and current_menu not in captured_meta_for:
            m = re.match(r"-\s+\*\*([^*]+)\*\*\s*:\s*(.+)$", ln)
            if m:
                label, value = m.group(1).strip(), m.group(2).strip()
                if label in {"Serving Hours", "Bread Options", "Wrap Base",
                             "Rice Base", "Pizza Sizes", "Pizza Base", "Cheese",
                             "Pasta Cook", "Eggs", "Milk", "Sugar",
                             "Customisation", "Note", "Portion Sizes",
                             "Sugar Levels (for shakes/smoothies)", "Ice",
                             "Milk Base", "Batter", "Dosa Options",
                             "Drink Upgrades", "Loyalty Benefit"}:
                    _emit(out,
                          f"What are the {label.lower()} for Menu {current_menu[0]} ({current_menu[1]}) at {QSR_BRAND}?",
                          f"For Menu {current_menu[0]} ({current_menu[1]}), {label}: {value}.",
                          "direct_fact")

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Airline (SkyJet Airways)
# ─────────────────────────────────────────────────────────────────────────────

def generate_airline_qna(text: str) -> list[dict]:
    out: list[dict] = []
    lines = text.splitlines()

    # Header
    header_block = []
    for ln in lines:
        if ln.startswith("## "):
            break
        header_block.append(ln)
    meta = _parse_top_metadata("\n".join(header_block))

    header_questions = {
        "Airline Name": (f"What is the name of the airline?", "The airline is {v}."),
        "Tagline": (f"What is the tagline of {AIRLINE_BRAND}?", f"The tagline of {AIRLINE_BRAND} is " + "{v}."),
        "Carrier Type": (f"What type of carrier is {AIRLINE_BRAND}?", f"{AIRLINE_BRAND} is a " + "{v}."),
        "Parent Company": (f"Who is the parent company of {AIRLINE_BRAND}?", "The parent company is {v}."),
        "IATA Code": (f"What is the IATA code of {AIRLINE_BRAND}?", "The IATA code is {v}."),
        "ICAO Code": (f"What is the ICAO code of {AIRLINE_BRAND}?", "The ICAO code is {v}."),
        "Callsign": (f"What is the callsign of {AIRLINE_BRAND}?", "The callsign is {v}."),
        "Founded": (f"When was {AIRLINE_BRAND} founded?", f"{AIRLINE_BRAND} was founded in " + "{v}."),
        "Primary Hub": (f"What is the primary hub of {AIRLINE_BRAND}?", "The primary hub is {v}."),
        "Secondary Hubs": (f"What are the secondary hubs of {AIRLINE_BRAND}?", "Secondary hubs: {v}."),
        "Fleet (Total: 84 aircraft)": (f"What is the fleet composition of {AIRLINE_BRAND}?", "Fleet: {v}."),
        "Network": (f"How large is the network of {AIRLINE_BRAND}?", "Network: {v}."),
        "Customer Service Hours": (f"What are the customer service hours of {AIRLINE_BRAND}?",
                                   "Customer service hours: {v}."),
        "Customer Service Numbers": (f"What are the customer service numbers for {AIRLINE_BRAND}?",
                                     "Customer service numbers: {v}."),
        "Email Support": (f"What is the email support address for {AIRLINE_BRAND}?",
                          "Email support: {v}."),
        "Live Chat": (f"How can I use live chat with {AIRLINE_BRAND}?",
                      "Live chat is available at {v}."),
        "Loyalty Program": (f"What is the loyalty program of {AIRLINE_BRAND}?",
                            "The loyalty program is {v}."),
        "Alliance": (f"Which alliance is {AIRLINE_BRAND} part of?",
                     "Alliance: {v}."),
        "GST Registration": (f"What is the GST registration of {AIRLINE_BRAND}?",
                             "GST registration: {v}."),
        "DGCA AOC Number": (f"What is the DGCA AOC number of {AIRLINE_BRAND}?",
                            "DGCA AOC number: {v}."),
        "Headquarters Address": (f"Where is {AIRLINE_BRAND} headquartered?",
                                 "Headquarters address: {v}."),
    }
    for label, (q, a_tpl) in header_questions.items():
        if label in meta:
            _emit(out, q, a_tpl.format(v=meta[label]), "direct_fact")

    # Tag system
    in_tags = False
    for ln in lines:
        if ln.startswith("## Tag System"):
            in_tags = True
            continue
        if in_tags and ln.startswith("## "):
            break
        if in_tags and ln.startswith("- "):
            for entry in re.split(r"\s+\|\s+", ln[2:]):
                m = re.match(r"\*\*\[([A-Z]+)\]\*\*\s*:\s*(.+)$", entry)
                if m:
                    code, meaning = m.group(1), m.group(2).strip()
                    _emit(out, f"What does the {code} tag mean at {AIRLINE_BRAND}?",
                          f"At {AIRLINE_BRAND}, [{code}] means: {meaning}.",
                          "direct_fact")

    # Section bullets
    section_re = re.compile(r"^##\s+(.+?)\s*$")
    bullet_re = re.compile(r"^-\s+\*\*([^*]+)\*\*\s*[:\u2014\-]\s*(.+)$")
    sub_bullet_re = re.compile(r"^\s{2,}-\s+\*\*([^*]+)\*\*\s*[:\u2014\-]\s*(.+)$")

    current_section: str | None = None
    skip_sections = {"Tag System"}

    for ln in lines:
        sm = section_re.match(ln)
        if sm:
            title = sm.group(1).strip()
            current_section = title if title not in skip_sections else None
            continue
        if current_section is None:
            continue

        sub = sub_bullet_re.match(ln)
        if sub:
            label, value = sub.group(1).strip(), sub.group(2).strip()
            _emit(out,
                  f"What does {label} mean in the {current_section.lower()} section for {AIRLINE_BRAND}?",
                  f"In {current_section} for {AIRLINE_BRAND}, {label}: {value}",
                  "direct_fact")
            continue

        bm = bullet_re.match(ln)
        if not bm:
            continue
        label, value = bm.group(1).strip(), bm.group(2).strip()
        # Skip the bare header summary bullets we already captured
        if label in header_questions and current_section == "":
            continue
        section_l = current_section.lower()

        # General "what is" question
        _emit(out,
              f"What is the {label.lower()} policy for {AIRLINE_BRAND}?",
              f"For {AIRLINE_BRAND}, {label}: {value}",
              "spanning")
        # "how" variant — useful for procedural lookups
        _emit(out,
              f"How does {label.lower()} work at {AIRLINE_BRAND}?",
              f"{label} at {AIRLINE_BRAND}: {value}",
              "spanning")
        # Section context question
        _emit(out,
              f"Where can I find information about {label.lower()} for {AIRLINE_BRAND}?",
              f"{label} is described under the '{current_section}' section: {value}",
              "spanning")

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def _write(path: Path, items: list[dict]) -> None:
    # De-duplicate by (question, answer)
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for it in items:
        key = (it["question"], it["answer"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    with path.open("w", encoding="utf-8") as fh:
        for it in unique:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"  wrote {len(unique):4d} Q&A -> {path}")


def main() -> None:
    tasks = [
        ("MegaRetail-M.md", "MegaRetail-M.qna.jsonl", generate_retail_qna),
        ("QuickBite-M.md", "QuickBite-M.qna.jsonl", generate_qsr_qna),
        ("SkyJet-S.md", "SkyJet-S.qna.jsonl", generate_airline_qna),
    ]
    for src, dst, fn in tasks:
        src_path = SAMPLES_DIR / src
        dst_path = SAMPLES_DIR / dst
        text = src_path.read_text(encoding="utf-8")
        print(f"Processing {src} ...")
        items = fn(text)
        _write(dst_path, items)


if __name__ == "__main__":
    main()
