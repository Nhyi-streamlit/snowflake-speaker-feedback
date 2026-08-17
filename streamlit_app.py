import os
import uuid
from datetime import datetime
from io import BytesIO

import streamlit as st

st.set_page_config(
    page_title="Rate this Talk — Snowflake Community Voices",
    page_icon="⭐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  html, body, [class*="st-"], .stTextInput input, .stSelectbox, .stMultiSelect,
  .stTextArea textarea, .stNumberInput input, .stRadio label, .stSlider,
  button, label, p, h1, h2, h3, span, div {
    font-family: 'Inter', sans-serif !important;
  }

  [data-testid="collapsedControl"] { display: none; }
  section[data-testid="stSidebar"] { display: none; }

  .page-hero {
    background: linear-gradient(135deg, #0E2346 0%, #1B3A6B 100%);
    padding: 40px 48px;
    border-radius: 16px;
    margin-bottom: 32px;
  }
  .page-hero .eyebrow {
    display: inline-block;
    background: rgba(41,181,232,0.2);
    color: #7ED8F6;
    border: 1px solid rgba(41,181,232,0.35);
    border-radius: 20px;
    padding: 3px 14px;
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 14px;
  }
  .page-hero h1 { color: #FFFFFF; font-size: 1.85rem; font-weight: 800; line-height: 1.25; margin-bottom: 8px; }
  .page-hero .talk-meta { color: #A8D8F0; font-size: 0.95rem; margin: 0; }
  .page-hero .talk-meta strong { color: #FFFFFF; }

  .section-label {
    display: inline-block;
    background: #EBF8FF;
    color: #29B5E8;
    border: 1px solid #BEE3F8;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .section-title { font-size: 1.05rem; font-weight: 700; color: #0E2346; margin: 2px 0; }
  .section-hint  { font-size: 0.85rem; color: #718096; margin-bottom: 16px; }

  .success-box {
    background: linear-gradient(135deg, #0E2346, #1B3A6B);
    border-radius: 16px;
    padding: 64px 48px;
    text-align: center;
  }
  .success-box h2 { color: #FFFFFF; font-size: 1.9rem; font-weight: 800; margin-bottom: 10px; }
  .success-box p  { color: #A8D8F0; font-size: 0.98rem; }

  .speaker-card {
    background: #F7FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 16px;
  }
  .qr-instructions {
    background: #EBF8FF;
    border: 1px solid #BEE3F8;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: 0.87rem;
    color: #2C5282;
    margin-top: 16px;
  }

  .star-row label { font-size: 1.4rem !important; }
</style>
""", unsafe_allow_html=True)


# ── Google Sheets helper ───────────────────────────────────────────────────────

def _access_token() -> str:
    import requests
    try:
        rt  = st.secrets.get("GOOGLE_REFRESH_TOKEN", "")
        cid = st.secrets.get("GOOGLE_CLIENT_ID", "")
        cs  = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
    except Exception:
        rt  = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
        cid = os.environ.get("GOOGLE_CLIENT_ID", "")
        cs  = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={"client_id": cid, "client_secret": cs, "refresh_token": rt, "grant_type": "refresh_token"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def save_feedback(data: dict) -> bool:
    import requests
    try:
        sid = st.secrets.get("GOOGLE_SPREADSHEET_ID", "")
    except Exception:
        sid = os.environ.get("GOOGLE_SPREADSHEET_ID", "")

    if not sid:
        return False

    try:
        token = _access_token()
        row = [
            data.get("submission_id", ""),
            data.get("submitted_at", ""),
            data.get("speaker_name", ""),
            data.get("event_name", ""),
            data.get("talk_title", ""),
            data.get("talk_date", ""),
            str(data.get("rating_overall", "")),
            str(data.get("rating_content", "")),
            str(data.get("rating_delivery", "")),
            str(data.get("rating_relevance", "")),
            data.get("most_valuable", ""),
            data.get("would_attend_again", ""),
            data.get("community_interest", ""),
            data.get("interested_areas", ""),
            data.get("respondent_name", ""),
            data.get("respondent_email", ""),
            data.get("other_feedback", ""),
        ]
        resp = requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sid}"
            f"/values/Talk%20Feedback!A:Q:append",
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            json={"values": [row]},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        return resp.status_code == 200
    except Exception:
        return False


# ── QR code generator ─────────────────────────────────────────────────────────

def make_qr(url: str) -> BytesIO:
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0E2346", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ── Routing ───────────────────────────────────────────────────────────────────

params       = st.query_params
mode         = params.get("mode", "feedback")
p_speaker    = params.get("speaker", "")
p_event      = params.get("event", "")
p_talk       = params.get("talk", "")

# If no speaker param is present and mode isn't explicitly set → show speaker setup
if not p_speaker and mode != "feedback":
    mode = "speaker"
elif not p_speaker and not p_event and not p_talk:
    mode = "speaker"

# Session state
if "feedback_submitted" not in st.session_state:
    st.session_state.feedback_submitted = False


# ════════════════════════════════════════════════════════════════════════════
# SPEAKER SETUP MODE — generate QR code for the talk
# ════════════════════════════════════════════════════════════════════════════

if mode == "speaker":
    st.markdown("""
<div class="page-hero">
  <div style="display:flex; align-items:center; gap:12px; margin-bottom:14px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/f/ff/Snowflake_Logo.svg"
         alt="Snowflake" height="30" style="filter:brightness(0) invert(1); flex-shrink:0;">
    <div class="eyebrow" style="margin-bottom:0;">Community Voices · Speaker Tools</div>
  </div>
  <h1>Generate Your Feedback QR Code</h1>
  <p class="talk-meta">Create a QR code for your last slide — attendees scan it to rate your talk in under 60 seconds.</p>
</div>
""", unsafe_allow_html=True)

    with st.form("speaker_setup"):
        st.markdown('<span class="section-label">Your Talk Details</span>', unsafe_allow_html=True)
        st.markdown('<p class="section-hint">Fill in the details below to generate a unique QR code for your session.</p>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            spk_name  = st.text_input("Your name *", placeholder="Aba Micah")
            spk_event = st.text_input("Event name *", placeholder="PyCon US 2026")
        with col2:
            spk_talk  = st.text_input("Talk title *", placeholder="Building AI Agents with Snowflake Cortex")

        generate = st.form_submit_button("Generate QR Code →", type="primary", use_container_width=True)

    if generate:
        if not all([spk_name.strip(), spk_event.strip(), spk_talk.strip()]):
            st.error("Please fill in all three fields.")
        else:
            try:
                base_url = st.secrets.get("APP_BASE_URL", "")
            except Exception:
                base_url = os.environ.get("APP_BASE_URL", "")

            if not base_url:
                base_url = "https://your-app-url.streamlit.app"

            import urllib.parse
            feedback_url = (
                f"{base_url}?"
                f"speaker={urllib.parse.quote(spk_name.strip())}&"
                f"event={urllib.parse.quote(spk_event.strip())}&"
                f"talk={urllib.parse.quote(spk_talk.strip())}"
            )

            qr_buf = make_qr(feedback_url)

            st.markdown('<div class="speaker-card">', unsafe_allow_html=True)

            img_col, info_col = st.columns([1, 2], gap="large")
            with img_col:
                st.image(qr_buf, use_container_width=True)

            with info_col:
                st.markdown(f"**Talk:** {spk_talk.strip()}")
                st.markdown(f"**Event:** {spk_event.strip()}")
                st.markdown(f"**Speaker:** {spk_name.strip()}")
                st.markdown("---")
                st.markdown("**Feedback link:**")
                st.code(feedback_url, language=None)
                st.download_button(
                    "⬇  Download QR code",
                    data=make_qr(feedback_url),
                    file_name=f"feedback-qr-{spk_name.strip().replace(' ','-').lower()}.png",
                    mime="image/png",
                    use_container_width=True,
                )

            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("""
<div class="qr-instructions">
  <strong>How to use this:</strong><br>
  1. Download the QR code PNG above<br>
  2. Drop it onto your final "Thank You" slide<br>
  3. Add a line like <em>"Scan to rate this talk — takes under a minute"</em><br>
  4. Responses go directly to the Snowflake Community team's tracker
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        '<p style="text-align:center; font-size:0.82rem; color:#A0AEC0;">Snowflake Community Voices · community@snowflake.com</p>',
        unsafe_allow_html=True
    )
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# FEEDBACK MODE — participant rates the talk
# ════════════════════════════════════════════════════════════════════════════

if st.session_state.feedback_submitted:
    st.markdown("""
<div class="success-box">
  <div style="font-size:3rem; margin-bottom:18px;">⭐</div>
  <h2>Thanks for the feedback!</h2>
  <p>Your score helps us recognize great community speakers<br>and improve the Snowflake Community Voices program.</p>
  <p style="margin-top:20px; font-size:0.85rem; opacity:0.7;">Want to speak at an event yourself?<br>
  Visit <strong>snowflake.com/community</strong> to learn about Data Superheroes & Streamlit Creators.</p>
</div>
""", unsafe_allow_html=True)
    st.stop()

# Hero — pre-fill from URL params
speaker_display = p_speaker or "this speaker"
event_display   = p_event   or "this event"
talk_display    = p_talk    or "this talk"

st.markdown(f"""
<div class="page-hero">
  <div style="display:flex; align-items:center; gap:12px; margin-bottom:14px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/f/ff/Snowflake_Logo.svg"
         alt="Snowflake" height="30" style="filter:brightness(0) invert(1); flex-shrink:0;">
    <div class="eyebrow" style="margin-bottom:0;">Community Voices · Talk Feedback</div>
  </div>
  <h1>Rate this Talk</h1>
  <p class="talk-meta">
    <strong>{talk_display}</strong><br>
    {speaker_display} · {event_display}
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown('<p style="font-size:0.9rem; color:#718096; margin-bottom:24px;">Takes under 60 seconds. Your feedback helps Snowflake recognize great community speakers and improve the program.</p>', unsafe_allow_html=True)

STAR_OPTIONS = ["★★★★★  Excellent (5)", "★★★★☆  Good (4)", "★★★☆☆  Average (3)", "★★☆☆☆  Fair (2)", "★☆☆☆☆  Poor (1)"]
STAR_VALUES  = {v: 5 - i for i, v in enumerate(STAR_OPTIONS)}

with st.form("feedback_form", clear_on_submit=False):

    # ── Section 1: Ratings ────────────────────────────────────────────────────
    st.markdown('<span class="section-label">Section 1 of 3</span>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Rate the Talk</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-hint">How would you rate each aspect of this session?</p>', unsafe_allow_html=True)

    r1, r2 = st.columns(2)
    with r1:
        overall   = st.selectbox("Overall  ⭐", STAR_OPTIONS, index=0)
        delivery  = st.selectbox("Speaker delivery  🎤", STAR_OPTIONS, index=0)
    with r2:
        content   = st.selectbox("Content quality  📚", STAR_OPTIONS, index=0)
        relevance = st.selectbox("Relevance to your work  🎯", STAR_OPTIONS, index=0)

    most_valuable = st.text_area(
        "What was the most valuable thing you learned?",
        placeholder="The demo showing how to build a Cortex AI pipeline was really practical...",
        height=90,
    )

    would_attend = st.radio(
        "Would you attend another talk by this speaker?",
        ["Yes, definitely", "Probably yes", "Not sure", "Probably not"],
        horizontal=True,
    )

    talk_date = st.date_input("Date of this talk", value="today")

    st.divider()

    # ── Section 2: Community signal ───────────────────────────────────────────
    st.markdown('<span class="section-label">Section 2 of 3</span>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Snowflake Community Interest</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-hint">Help us understand if this talk sparked any interest in Snowflake.</p>', unsafe_allow_html=True)

    community_interest = st.radio(
        "Did this talk make you want to explore Snowflake or get involved in the community?",
        [
            "Yes — I'm new to Snowflake and want to learn more",
            "Yes — I'm already a Snowflake user and want to get more involved",
            "I'm already part of the Data Superheroes / Creators community",
            "Not particularly",
        ],
    )

    interested_areas = []
    if "Yes" in community_interest:
        interested_areas = st.multiselect(
            "What Snowflake area interests you most? (optional)",
            [
                "Cortex AI / LLM Functions",
                "Cortex Agents",
                "Cortex Code (CoCo)",
                "Snowpark / Python",
                "Streamlit in Snowflake",
                "Data Engineering / Pipelines",
                "Data Sharing / Marketplace",
                "AI / ML on Snowflake",
                "Data Governance",
                "General — just want to explore",
            ],
        )

    st.divider()

    # ── Section 3: Optional contact ───────────────────────────────────────────
    st.markdown('<span class="section-label">Section 3 of 3</span>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Your Info (optional)</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-hint">Only needed if you want the Snowflake Community team to follow up with you.</p>', unsafe_allow_html=True)

    oc1, oc2 = st.columns(2)
    with oc1:
        respondent_name = st.text_input("Your name", placeholder="Optional")
    with oc2:
        respondent_email = st.text_input("Your email", placeholder="Optional — to receive community updates")

    other_feedback = st.text_area(
        "Any other feedback for the speaker or program?",
        placeholder="Optional — share anything else you'd like the speaker or Snowflake Community team to know.",
        height=80,
    )

    st.markdown("")
    submit = st.form_submit_button("Submit Feedback →", type="primary", use_container_width=True)

if submit:
    payload = {
        "submission_id":    str(uuid.uuid4()),
        "submitted_at":     datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "speaker_name":     p_speaker,
        "event_name":       p_event,
        "talk_title":       p_talk,
        "talk_date":        str(talk_date),
        "rating_overall":   STAR_VALUES[overall],
        "rating_content":   STAR_VALUES[content],
        "rating_delivery":  STAR_VALUES[delivery],
        "rating_relevance": STAR_VALUES[relevance],
        "most_valuable":    most_valuable.strip(),
        "would_attend_again": would_attend,
        "community_interest": community_interest,
        "interested_areas": ", ".join(interested_areas),
        "respondent_name":  respondent_name.strip(),
        "respondent_email": respondent_email.strip(),
        "other_feedback":   other_feedback.strip(),
    }
    with st.spinner("Submitting…"):
        ok = save_feedback(payload)
    if ok:
        st.session_state.feedback_submitted = True
        st.rerun()
    else:
        st.warning("Could not save your feedback right now. Please try again.")

st.markdown("---")
st.markdown(
    '<p style="text-align:center; font-size:0.82rem; color:#A0AEC0;">Snowflake Community Voices · community@snowflake.com</p>',
    unsafe_allow_html=True
)
