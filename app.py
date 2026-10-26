import json
import re
import csv
import io
from datetime import datetime
from pathlib import Path

import streamlit as st

# ============================================================
# BrandSure — Brand Governance & Content Review
# Run with: py -m streamlit run app.py
# ============================================================

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
GUIDELINES_FILE = DATA_DIR / "guidelines.json"
HISTORY_FILE = DATA_DIR / "history.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_GUIDELINES = [
    {
        "id": "RULE-001",
        "title": "Avoid unsupported guarantees",
        "term": "guaranteed",
        "severity": "High",
        "category": "Claims & Compliance",
        "description": "Do not promise guaranteed results unless the claim is approved and supported by evidence.",
        "suggestion": "Use qualified language such as 'designed to help' or add approved supporting evidence.",
        "enabled": True,
    },
    {
        "id": "RULE-002",
        "title": "Avoid absolute claims",
        "term": "100% risk-free",
        "severity": "High",
        "category": "Claims & Compliance",
        "description": "Avoid absolute safety or risk claims unless they have been formally approved.",
        "suggestion": "Explain the specific safeguards or limitations instead of making an absolute claim.",
        "enabled": True,
    },
    {
        "id": "RULE-003",
        "title": "Use a professional tone",
        "term": "OMG",
        "severity": "Medium",
        "category": "Tone of Voice",
        "description": "Avoid overly casual slang in official brand communications.",
        "suggestion": "Replace slang with a clear, professional expression.",
        "enabled": True,
    },
    {
        "id": "RULE-004",
        "title": "Avoid competitor attacks",
        "term": "our competitors are terrible",
        "severity": "Medium",
        "category": "Brand Reputation",
        "description": "Do not insult competitors or make broad negative statements about them.",
        "suggestion": "Focus on your own product's verified strengths and customer benefits.",
        "enabled": True,
    },
]


def read_json(path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                value = json.load(f)
                return value
    except (json.JSONDecodeError, OSError):
        st.warning(f"Could not read {path.name}. A fresh default will be used.")
    return default.copy() if isinstance(default, list) else default


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if not GUIDELINES_FILE.exists():
    write_json(GUIDELINES_FILE, DEFAULT_GUIDELINES)
if not HISTORY_FILE.exists():
    write_json(HISTORY_FILE, [])

if "guidelines" not in st.session_state:
    st.session_state.guidelines = read_json(GUIDELINES_FILE, DEFAULT_GUIDELINES)
if "history" not in st.session_state:
    st.session_state.history = read_json(HISTORY_FILE, [])


def save_guidelines():
    write_json(GUIDELINES_FILE, st.session_state.guidelines)


def save_history():
    write_json(HISTORY_FILE, st.session_state.history)


def next_rule_id():
    nums = []
    for item in st.session_state.guidelines:
        match = re.search(r"(\d+)$", item.get("id", ""))
        if match:
            nums.append(int(match.group(1)))
    return f"RULE-{max(nums, default=0) + 1:03d}"


def review_text(content):
    findings = []
    active_rules = [g for g in st.session_state.guidelines if g.get("enabled", True)]
    for rule in active_rules:
        term = rule.get("term", "").strip()
        if not term:
            continue
        try:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
        except re.error:
            continue
        for match in pattern.finditer(content):
            start, end = match.span()
            left = content.rfind("\n", 0, start)
            right = content.find("\n", end)
            if left < 0:
                left = max(0, content.rfind(". ", 0, start) + 2)
            else:
                left += 1
            if right < 0:
                right = len(content)
            snippet = content[left:right].strip()
            if len(snippet) > 240:
                snippet_start = max(left, start - 90)
                snippet_end = min(right, end + 110)
                snippet = content[snippet_start:snippet_end].strip()
                if snippet_start > left:
                    snippet = "…" + snippet
                if snippet_end < right:
                    snippet = snippet + "…"
            findings.append({
                "rule_id": rule.get("id", "RULE"),
                "rule_title": rule.get("title", "Brand rule"),
                "term": term,
                "severity": rule.get("severity", "Medium"),
                "category": rule.get("category", "General"),
                "description": rule.get("description", ""),
                "suggestion": rule.get("suggestion", ""),
                "evidence": snippet,
                "matched_text": match.group(0),
                "start": start,
                "end": end,
                "status": "Open",
            })
    findings.sort(key=lambda x: ({"High": 0, "Medium": 1, "Low": 2}.get(x["severity"], 3), x["start"]))
    return findings


def suggest_rewrite(content, findings):
    # Only known, deliberately curated substitutions are automatic. Custom rules
    # remain suggestions for a human editor to avoid broken grammar or false claims.
    replacements = {
        "RULE-001": ("guaranteed", "designed to help"),
        "RULE-002": ("100% risk-free", "designed with safeguards"),
        "RULE-003": ("OMG", "Importantly"),
        "RULE-004": ("our competitors are terrible", "our product offers distinct benefits"),
    }
    updated = content
    changes = []
    candidates = []
    for finding in findings:
        pair = replacements.get(finding.get("rule_id"))
        if pair and finding.get("start") is not None and finding.get("end") is not None:
            candidates.append((finding["start"], finding["end"], pair[1], finding.get("matched_text", finding.get("term", ""))))
    accepted = []
    previous_start = len(content) + 1
    for start, end, replacement, original in sorted(candidates, key=lambda item: item[0], reverse=True):
        if end > previous_start:
            continue
        accepted.append((start, end, replacement, original))
        previous_start = start
    for start, end, replacement, original in accepted:
        updated = updated[:start] + replacement + updated[end:]
        changes.append(f"Replaced '{original}' with '{replacement}'.")
    return updated, changes


st.set_page_config(
    page_title="BrandSure | Brand Governance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root {
  --ink:#172033; --muted:#69758b; --line:#e5eaf3; --paper:#ffffff;
  --blue:#4f46e5; --blue-dark:#3730a3; --mint:#dffaf1; --navy:#10172b;
}
html, body, [class*="css"], [data-testid="stAppViewContainer"] { font-family:'DM Sans',sans-serif; }
.stApp { background:linear-gradient(145deg,#f7f8ff 0%,#f4f7fb 48%,#f1fbf8 100%); color:var(--ink); }
[data-testid="stHeader"] { background:rgba(247,248,255,.82); }
.block-container { max-width:1450px; padding-top:1.7rem; padding-bottom:3.2rem; }
h1,h2,h3,h4,p,label,li,.stMarkdown,[data-testid="stMetricLabel"] { color:var(--ink); }
h1,h2,h3,h4 { font-family:'Manrope',sans-serif !important; letter-spacing:-.035em; }
h1 { font-weight:800 !important; font-size:2.35rem !important; }
h2 { font-weight:800 !important; }
h3 { font-weight:750 !important; }
p { line-height:1.62; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#11182d 0%,#18294a 100%); border-right:1px solid #273658; }
[data-testid="stSidebar"] * { color:#f7f9ff !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 { font-size:1.5rem; letter-spacing:-.04em; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#bac8e2 !important; }
[data-testid="stSidebar"] hr { border-color:#344361; }
[data-testid="stSidebar"] .stRadio > label { color:#9eafd0 !important; font-size:.72rem; font-weight:800; letter-spacing:.12em; }
[data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap:5px; }
[data-testid="stSidebar"] .stRadio [role="radio"] { padding:10px 12px; border-radius:12px; transition:background .18s ease; }
[data-testid="stSidebar"] .stRadio [role="radio"]:hover { background:#26395d; }
.hero { position:relative; overflow:hidden; background:linear-gradient(115deg,#171d3b 0%,#3730a3 55%,#4f46e5 100%); color:white; padding:36px 38px; border-radius:26px; margin-bottom:24px; box-shadow:0 18px 42px rgba(55,48,163,.2); }
.hero:after { content:''; position:absolute; width:260px; height:260px; border-radius:50%; right:-50px; top:-110px; border:1px solid rgba(255,255,255,.18); box-shadow:0 0 0 28px rgba(255,255,255,.045),0 0 0 58px rgba(255,255,255,.035); }
.hero h1,.hero p,.hero span { color:white !important; position:relative; z-index:1; }
.hero h1 { font-size:2.75rem !important; margin:.3rem 0 .55rem 0; }
.hero p { margin:5px 0; color:#e4e9ff !important; }
.eyebrow { text-transform:uppercase; font-size:.72rem; font-weight:800; letter-spacing:.16em; color:#bfcaff !important; }
.card { background:rgba(255,255,255,.92); border:1px solid rgba(220,228,242,.95); border-radius:19px; padding:22px 24px; box-shadow:0 8px 24px rgba(31,45,80,.045); margin-bottom:15px; transition:transform .18s ease,box-shadow .18s ease; }
.card:hover { transform:translateY(-2px); box-shadow:0 14px 32px rgba(31,45,80,.08); }
.card h3,.card p { margin-top:0; }
.small-muted { color:var(--muted) !important; font-size:.92rem; }
.pill { display:inline-block; border-radius:999px; padding:5px 11px; font-size:.76rem; font-weight:800; background:#eeedff; color:#4338ca !important; }
[data-testid="stMetric"] { background:rgba(255,255,255,.94); border:1px solid var(--line); border-radius:18px; padding:19px 21px; box-shadow:0 7px 22px rgba(31,45,80,.045); }
[data-testid="stMetricLabel"] { color:#69758b !important; font-size:.85rem; font-weight:700; }
[data-testid="stMetricValue"] { color:#24204f !important; font-family:'Manrope',sans-serif; font-weight:800; letter-spacing:-.04em; }
[data-testid="stMetricDelta"] { font-weight:700; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button { border-radius:12px !important; border:1px solid #d8def0 !important; background:#fff !important; color:#312e81 !important; font-weight:800 !important; min-height:2.8rem; box-shadow:0 3px 10px rgba(30,41,80,.05); transition:all .18s ease; }
.stButton > button p,.stButton > button span,.stButton > button div,.stDownloadButton > button p,.stDownloadButton > button span { color:inherit !important; }
.stButton > button:hover,.stDownloadButton > button:hover { background:#f0efff !important; border-color:#a5b4fc !important; transform:translateY(-1px); }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primary"], .stDownloadButton > button[kind="primary"] { background:linear-gradient(110deg,#4f46e5,#6366f1) !important; color:#fff !important; border-color:#4f46e5 !important; box-shadow:0 7px 17px rgba(79,70,229,.2); }
.stButton > button[kind="primary"] p,.stButton > button[kind="primary"] span,.stButton > button[kind="primary"] div,[data-testid="stFormSubmitButton"] > button[kind="primary"] * { color:#fff !important; }
.stButton > button[kind="primary"]:hover,[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover { background:#4338ca !important; border-color:#4338ca !important; }
.stTextInput input,.stTextArea textarea,.stNumberInput input { background:#fff !important; color:#172033 !important; border:1px solid #d9e0ed !important; border-radius:12px !important; }
.stTextInput input:focus,.stTextArea textarea:focus { border-color:#818cf8 !important; box-shadow:0 0 0 3px rgba(99,102,241,.12) !important; }
.stSelectbox div[data-baseweb="select"] > div,.stMultiSelect div[data-baseweb="select"] > div { background:white; color:#172033; border-radius:12px; border-color:#d9e0ed; }
[data-testid="stExpander"] { background:rgba(255,255,255,.8); border:1px solid var(--line); border-radius:15px; overflow:hidden; }
[data-testid="stExpander"] summary { font-weight:700; }
[data-testid="stDataFrame"],[data-testid="stTable"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
div[data-testid="stAlert"] { border-radius:14px; border:1px solid var(--line); }
.stProgress > div > div { background:linear-gradient(90deg,#4f46e5,#2dd4bf); }
hr { border-color:#e2e8f2; }
footer { visibility:hidden; }
@media (max-width: 700px) { .block-container { padding-top:1rem; } .hero { padding:25px 22px; border-radius:20px; } .hero h1 { font-size:2.05rem !important; } h1 { font-size:1.9rem !important; } .card { padding:17px; } }
</style>
""", unsafe_allow_html=True)


def page_header(title, subtitle, icon="✨"):
    st.markdown(f"<div style='margin-bottom:18px'><div class='eyebrow' style='color:#2563eb !important'>{icon} BRAND GOVERNANCE WORKSPACE</div><h1 style='margin:.25rem 0'>{title}</h1><p class='small-muted' style='margin-top:0'>{subtitle}</p></div>", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("## 🛡️ BrandSure")
    st.markdown("**Brand governance workspace**")
    st.markdown("<p style='font-size:.86rem'>Review before you publish. Keep humans in control.</p>", unsafe_allow_html=True)
    st.divider()
    page = st.radio(
        "NAVIGATION",
        ["Dashboard", "Review Content", "Brand Guidelines", "Review History", "Insights & Export", "About Project"],
        label_visibility="visible",
    )
    st.divider()
    st.markdown("### Review status")
    st.markdown(f"📋 **{len(st.session_state.guidelines)}** total rules")
    st.markdown(f"📝 **{len(st.session_state.history)}** saved reviews")
    st.caption("Prototype • Local data storage")


# Dashboard
if page == "Dashboard":
    st.markdown("""
    <div class="hero">
      <div class="eyebrow">TRUSTED CONTENT STARTS HERE</div>
      <h1>🛡️ BrandSure</h1>
      <p style="font-size:1.08rem">AI-assisted brand governance. Review before you publish.</p>
      <p>Detect issues · Explain the rules · Suggest improvements · Keep humans in control</p>
    </div>
    """, unsafe_allow_html=True)
    total_reviews = len(st.session_state.history)
    open_findings = sum(1 for r in st.session_state.history for f in r.get("findings", []) if f.get("status", "Open") == "Open")
    approved = sum(1 for r in st.session_state.history if r.get("decision") == "Approved")
    active_rules = sum(1 for g in st.session_state.guidelines if g.get("enabled", True))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total reviews", total_reviews)
    c2.metric("Active brand rules", active_rules)
    c3.metric("Open findings", open_findings)
    c4.metric("Approved reviews", approved)

    st.markdown("## 🚀 Quick actions")
    a, b, c = st.columns(3)
    with a:
        st.markdown("<div class='card'><h3>📝 Review content</h3><p class='small-muted'>Check marketing copy against your configured brand rules.</p></div>", unsafe_allow_html=True)
        if st.button("Start a content review", type="primary", use_container_width=True):
            st.session_state.quick_nav = "Review Content"
            st.rerun()
    with b:
        st.markdown("<div class='card'><h3>📚 Brand guidelines</h3><p class='small-muted'>Manage approved terminology, tone and policy rules.</p></div>", unsafe_allow_html=True)
        if st.button("Manage brand rules", use_container_width=True):
            st.session_state.quick_nav = "Brand Guidelines"
            st.rerun()
    with c:
        st.markdown("<div class='card'><h3>📊 Insights & export</h3><p class='small-muted'>Review trends and download your review records.</p></div>", unsafe_allow_html=True)
        if st.button("View insights", use_container_width=True):
            st.session_state.quick_nav = "Insights & Export"
            st.rerun()

    # Quick-action navigation rerun state
    if "quick_nav" in st.session_state:
        st.info(f"Use the left navigation to open **{st.session_state.quick_nav}**. (The navigation menu remains the source of truth.)")
        del st.session_state.quick_nav

    st.markdown("## 🕘 Recent activity")
    if not st.session_state.history:
        st.info("No reviews yet. Start with **Review Content** to create your first review.")
    else:
        for item in reversed(st.session_state.history[-5:]):
            decision = item.get("decision", "Pending")
            st.markdown(f"<div class='card'><b>{item.get('title') or 'Untitled review'}</b><br><span class='small-muted'>{item.get('created_at','')} · {len(item.get('findings', []))} finding(s) · Decision: {decision}</span></div>", unsafe_allow_html=True)


# Review Content
elif page == "Review Content":
    page_header("Review content", "Paste draft copy, run the rule checker, then record a human review decision.", "📝")
    with st.form("review_form"):
        title = st.text_input("Content title", placeholder="e.g. Summer campaign landing page")
        channel = st.selectbox("Publication channel", ["Website", "Social media", "Email campaign", "Advertisement", "Blog / article", "Other"])
        content = st.text_area("Content to review", height=220, placeholder="Paste your marketing copy here…")
        submitted = st.form_submit_button("🔎 Check against brand rules", type="primary", use_container_width=True)

    if submitted:
        if not content.strip():
            st.error("Please paste some content before running the review.")
        else:
            findings = review_text(content)
            rewritten, rewrite_changes = suggest_rewrite(content, findings)
            record = {
                "id": f"REV-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "title": title.strip() or "Untitled review",
                "channel": channel,
                "content": content,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "findings": findings,
                "decision": "Pending",
                "reviewer_comment": "",
                "suggested_rewrite": rewritten,
                "rewrite_changes": rewrite_changes,
            }
            st.session_state.history.append(record)
            save_history()
            st.session_state.latest_review_id = record["id"]
            st.rerun()

    latest_id = st.session_state.get("latest_review_id")
    record = next((r for r in reversed(st.session_state.history) if r.get("id") == latest_id), None)
    if record:
        st.divider()
        st.markdown(f"## Results: {record['title']}")
        high = sum(1 for f in record["findings"] if f["severity"] == "High")
        medium = sum(1 for f in record["findings"] if f["severity"] == "Medium")
        low = sum(1 for f in record["findings"] if f["severity"] == "Low")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total findings", len(record["findings"]))
        m2.metric("High", high)
        m3.metric("Medium", medium)
        m4.metric("Low", low)
        if not record["findings"]:
            st.success("No configured rule violations were detected. This does not guarantee that the content is factually correct or fully compliant.")
        else:
            st.warning("Potential issues found. Review each explanation before deciding whether to publish.")
            for idx, finding in enumerate(record["findings"], start=1):
                with st.expander(f"{idx}. {finding['severity']} · {finding['rule_title']} — “{finding['term']}”", expanded=(idx == 1)):
                    st.markdown(f"**Category:** {finding['category']}  ·  **Rule ID:** {finding['rule_id']}")
                    st.markdown("**Evidence:**")
                    st.code(finding.get("evidence", ""), language=None)
                    st.markdown(f"**Why it was flagged:** {finding['description']}")
                    st.markdown(f"**Suggested action:** {finding['suggestion']}")
        st.markdown("## ✍️ Suggested rewrite")
        st.caption("This is a basic rules-based suggestion, not an AI-generated or fact-verified rewrite. Check it before use.")
        st.text_area("Editable suggested copy", value=record.get("suggested_rewrite", record["content"]), height=160, key=f"rewrite_{record['id']}")
        if record.get("rewrite_changes"):
            for change in record["rewrite_changes"]:
                st.write("• " + change)
        else:
            st.info("No automatic substitutions were made. Use the finding suggestions above to edit the copy manually.")
        st.markdown("## 👤 Human review decision")
        with st.form(f"decision_form_{record['id']}"):
            current_decision = st.selectbox("Decision", ["Pending", "Approved", "Changes Requested", "Rejected"], index=["Pending", "Approved", "Changes Requested", "Rejected"].index(record.get("decision", "Pending")))
            comment = st.text_area("Reviewer comments", value=record.get("reviewer_comment", ""), placeholder="Explain the decision or list required changes…")
            save_decision = st.form_submit_button("Save review decision", type="primary")
        if save_decision:
            record["decision"] = current_decision
            record["reviewer_comment"] = comment
            record["suggested_rewrite"] = st.session_state.get(f"rewrite_{record['id']}", record.get("suggested_rewrite", record["content"]))
            save_history()
            st.success("Review decision saved.")
            st.rerun()


# Brand Guidelines
elif page == "Brand Guidelines":
    page_header("Brand guidelines", "Create and manage the rules that your content review checks against.", "📚")
    with st.expander("➕ Add a new brand rule", expanded=True):
        with st.form("add_rule_form", clear_on_submit=True):
            new_title = st.text_input("Rule name", placeholder="e.g. Avoid unapproved discount claims")
            new_term = st.text_input("Word or phrase to flag", placeholder="e.g. 90% guaranteed")
            col1, col2 = st.columns(2)
            with col1:
                new_severity = st.selectbox("Severity", ["High", "Medium", "Low"])
                new_category = st.selectbox("Category", ["Claims & Compliance", "Tone of Voice", "Terminology", "Brand Reputation", "Formatting", "Other"])
            with col2:
                new_description = st.text_input("Why does this rule exist?", placeholder="Explain the brand policy")
                new_suggestion = st.text_input("Recommended action", placeholder="What should the writer do?")
            add_rule = st.form_submit_button("Add rule", type="primary", use_container_width=True)
        if add_rule:
            if not new_title.strip() or not new_term.strip():
                st.error("Rule name and flagged word/phrase are required.")
            elif any(g.get("term", "").casefold() == new_term.strip().casefold() for g in st.session_state.guidelines):
                st.error("A rule for that exact phrase already exists.")
            else:
                st.session_state.guidelines.append({
                    "id": next_rule_id(),
                    "title": new_title.strip(),
                    "term": new_term.strip(),
                    "severity": new_severity,
                    "category": new_category,
                    "description": new_description.strip() or "Review this phrase against the approved brand policy.",
                    "suggestion": new_suggestion.strip() or "Edit the phrase to follow the approved brand guidelines.",
                    "enabled": True,
                })
                save_guidelines()
                st.success("Brand rule added successfully.")
                st.rerun()

    st.markdown("## Existing rules")
    if not st.session_state.guidelines:
        st.info("No rules yet. Add your first rule above.")
    for rule in st.session_state.guidelines:
        with st.container(border=True):
            left, right = st.columns([5, 1.4])
            with left:
                status = "Active" if rule.get("enabled", True) else "Disabled"
                st.markdown(f"### {rule.get('title','Untitled rule')}  ` {rule.get('id','')} `")
                st.markdown(f"**Flag:** `{rule.get('term','')}`  ·  **Severity:** {rule.get('severity','Medium')}  ·  **Category:** {rule.get('category','Other')}  ·  **Status:** {status}")
                st.write(rule.get("description", ""))
                st.caption("Suggested action: " + rule.get("suggestion", ""))
            with right:
                enabled = st.toggle("Enabled", value=rule.get("enabled", True), key=f"enabled_{rule.get('id')}")
                if enabled != rule.get("enabled", True):
                    rule["enabled"] = enabled
                    save_guidelines()
                    st.rerun()
                if st.button("Delete rule", key=f"delete_{rule.get('id')}", use_container_width=True):
                    st.session_state.guidelines = [g for g in st.session_state.guidelines if g.get("id") != rule.get("id")]
                    save_guidelines()
                    st.rerun()
    st.download_button("⬇️ Download guidelines (JSON)", data=json.dumps(st.session_state.guidelines, indent=2), file_name="brandsure_guidelines.json", mime="application/json")


# Review History
elif page == "Review History":
    page_header("Review history", "Find earlier reviews and inspect the decision trail.", "🕘")
    if not st.session_state.history:
        st.info("No review history yet. Run a review to create your first record.")
    else:
        search = st.text_input("Search reviews", placeholder="Search by title, channel, content or decision…")
        decision_filter = st.selectbox("Filter by decision", ["All", "Pending", "Approved", "Changes Requested", "Rejected"])
        records = list(reversed(st.session_state.history))
        if search.strip():
            q = search.casefold()
            records = [r for r in records if q in (r.get("title", "") + " " + r.get("channel", "") + " " + r.get("content", "") + " " + r.get("decision", "")).casefold()]
        if decision_filter != "All":
            records = [r for r in records if r.get("decision", "Pending") == decision_filter]
        st.caption(f"{len(records)} review(s) match your filters.")
        for record in records:
            with st.expander(f"{record.get('title','Untitled review')} · {record.get('created_at','')} · {record.get('decision','Pending')}"):
                st.markdown(f"**Review ID:** {record.get('id','')}  \n**Channel:** {record.get('channel','')}  \n**Findings:** {len(record.get('findings', []))}")
                st.text_area("Original content", value=record.get("content", ""), height=100, key=f"history_content_{record.get('id')}")
                if record.get("findings"):
                    for finding in record["findings"]:
                        st.markdown(f"- **{finding.get('severity','')}** — {finding.get('rule_title','')}: {finding.get('term','')}")
                else:
                    st.write("No configured rule matches were detected.")
                st.markdown("**Reviewer comment:** " + (record.get("reviewer_comment") or "No comment recorded."))
                new_decision = st.selectbox("Update decision", ["Pending", "Approved", "Changes Requested", "Rejected"], index=["Pending", "Approved", "Changes Requested", "Rejected"].index(record.get("decision", "Pending")), key=f"history_decision_{record.get('id')}")
                new_comment = st.text_input("Update reviewer comment", value=record.get("reviewer_comment", ""), key=f"history_comment_{record.get('id')}")
                if st.button("Save changes", key=f"history_save_{record.get('id')}", type="primary"):
                    record["decision"] = new_decision
                    record["reviewer_comment"] = new_comment
                    save_history()
                    st.success("Review updated.")
                    st.rerun()


# Insights & Export
elif page == "Insights & Export":
    page_header("Insights & export", "See recurring issues and download records for your hackathon demo.", "📊")
    history = st.session_state.history
    total = len(history)
    all_findings = [f for r in history for f in r.get("findings", [])]
    approved = sum(1 for r in history if r.get("decision") == "Approved")
    needs_work = sum(1 for r in history if r.get("decision") in ["Changes Requested", "Rejected"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reviews", total)
    c2.metric("Flagged matches", len(all_findings))
    c3.metric("Approved", approved)
    c4.metric("Needs work", needs_work)
    st.markdown("## Most frequently flagged phrases")
    counts = {}
    for finding in all_findings:
        key = finding.get("term", "(unknown)")
        counts[key] = counts.get(key, 0) + 1
    if counts:
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        st.bar_chart({"Matches": {k: v for k, v in sorted_counts}})
    else:
        st.info("No findings to chart yet. Run some sample reviews first.")
    st.markdown("## Export records")
    export_records = []
    for r in history:
        export_records.append({
            "review_id": r.get("id", ""),
            "title": r.get("title", ""),
            "channel": r.get("channel", ""),
            "created_at": r.get("created_at", ""),
            "decision": r.get("decision", "Pending"),
            "finding_count": len(r.get("findings", [])),
            "reviewer_comment": r.get("reviewer_comment", ""),
            "content": r.get("content", ""),
        })
    csv_buffer = io.StringIO()
    fieldnames = ["review_id", "title", "channel", "created_at", "decision", "finding_count", "reviewer_comment", "content"]
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(export_records)
    st.download_button("⬇️ Download review history (CSV)", data=csv_buffer.getvalue(), file_name="brandsure_review_history.csv", mime="text/csv", type="primary")
    st.download_button("⬇️ Download full backup (JSON)", data=json.dumps({"guidelines": st.session_state.guidelines, "history": history}, indent=2, ensure_ascii=False), file_name="brandsure_backup.json", mime="application/json")


# About
elif page == "About Project":
    page_header("About BrandSure", "A transparent, human-in-the-loop brand governance prototype.", "ℹ️")
    st.markdown("""
    <div class="card">
      <h3>🎯 Problem</h3>
      <p>Teams publish content through employees, agencies and AI tools. Inconsistent language, risky claims and outdated messaging can harm trust.</p>
      <h3>💡 Solution</h3>
      <p>BrandSure checks submitted copy against a configurable library of approved rules, explains why a phrase was flagged, and records a human decision before publication.</p>
      <h3>🧩 Core workflow</h3>
      <p>Draft content → Match brand rules → Explain findings → Review suggested changes → Human approval decision → Export the audit trail.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("## Technology")
    t1, t2, t3 = st.columns(3)
    t1.markdown("<div class='card'><h3>🖥️ Interface</h3><p>Python + Streamlit</p></div>", unsafe_allow_html=True)
    t2.markdown("<div class='card'><h3>🔎 Review engine</h3><p>Python regular-expression phrase matching</p></div>", unsafe_allow_html=True)
    t3.markdown("<div class='card'><h3>💾 Storage</h3><p>Local JSON files + CSV/JSON export</p></div>", unsafe_allow_html=True)
    st.warning("Prototype limitation: this version uses deterministic rule matching, not a connected LLM. It cannot independently verify factual claims, inspect images, authenticate users or provide legal/compliance certification. A human must make the final publication decision.")
    st.markdown("## Suggested next-round improvements")
    st.markdown("""
    1. **Image and visual review:** check uploaded creative assets against logo, color and visual identity rules.
    2. **Team analytics dashboard:** compare recurring violations by channel, rule category and review status.
    3. **Production reliability:** add authentication, database storage, tests, logging and deployment monitoring.
    """)

st.markdown("<div style='text-align:center;color:#718096;font-size:.82rem;padding:26px 0 0'>BrandSure · Human-in-the-loop brand governance · Prototype</div>", unsafe_allow_html=True)
