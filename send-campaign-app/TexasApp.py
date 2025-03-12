import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import random
from urllib.parse import urlparse

# ------------------------------
# BIGMAILER CREDENTIALS & CONFIG
# ------------------------------
# Instead of hardcoding them:
# BIGMAILER_BRAND_ID = "..."
# BIGMAILER_API_KEY  = "..."
# We load them from secrets:
BIGMAILER_BRAND_ID = st.secrets["bigmailer"]["brand_id"]
BIGMAILER_API_KEY  = st.secrets["bigmailer"]["api_key"]

lists_config = {
    "MAIN": "f8279af2-8947-48d7-a5b3-87ab35675404",
    "WARMING1": "2085bf1c-2fde-4fe4-a9c7-ccb36bd00459",
    "WARMING2": "c440fda0-02fc-49cd-b6b3-bb8cce48cc46",
    "WARMING3": "43843072-1cb2-489f-86fc-0fea4304035d",
    "WARMING4": "7d7b4148-49bd-4706-85bd-a264a50b50d0",
    "WARMING5": "641fb003-638a-431f-ad08-b50243bce761"
}

possible_senders = ["None", "info@txreport.com", "info@txrpt.com"]

def scrape_headlines():
    url = 'https://txreport.com'
    response = requests.get(url)
    if response.status_code != 200:
        return {"error": "Failed to fetch headlines. Please try again later."}

    soup = BeautifulSoup(response.text, 'html.parser')
    sections = {
        'TOP_HEADLINES': '.left-side-topnews a',
        'LEFT_HEADLINES': '.leftsidebarstory a',
        'MIDDLE_HEADLINES': '.middlesidebarstory a',
        'RIGHT_HEADLINES': '.rightsidebarstory a'
    }

    scraped_headlines = {key: [] for key in sections.keys()}
    all_headlines = {}
    todays_front_pages_summary = (
        'Today\'s Front Pages - Austin, Houston, DFW, and more! '
        '<a href="https://txreport.com/" target="_blank">(link)</a><br><br>'
    )

    see_more_links = {}
    for section, selector in sections.items():
        headlines = soup.select(selector)
        if section != 'TOP_HEADLINES' and len(headlines) > 5:
            next_story = headlines[5]
            next_story_link = f'https://txreport.com/#[link]{next_story.get("id", "000000")}'
            see_more_links[section] = (
                f'See More... <a href="{next_story_link}" target="_blank">(link)</a><br><br>'
            )

        if section != 'TOP_HEADLINES':
            headlines = headlines[:5]

        for h in headlines:
            text = h.text.strip()
            if "Advertise on Texas Report" in text or not text:
                continue
            if text.startswith("TODAY’S ") and "FRONT PAGE" in text:
                continue

            if text not in all_headlines:
                all_headlines[text] = 1
            else:
                all_headlines[text] += 1

            post_id = h.get('id', '000000')
            link = f'https://txreport.com/#[link]{post_id}'
            if all_headlines[text] <= len(sections):
                scraped_headlines[section].append(
                    f'{text}<a href="{link}" target="_blank">(link)</a><br><br>'
                )

    scraped_headlines['TOP_HEADLINES'].append(todays_front_pages_summary)
    for section in ['LEFT_HEADLINES', 'MIDDLE_HEADLINES', 'RIGHT_HEADLINES']:
        if section in see_more_links:
            scraped_headlines[section].append(see_more_links[section])
    return scraped_headlines

def get_ads():
    sheet_csv_url = (
        "https://docs.google.com/spreadsheets/d/"
        "15vV7yzNiaW9pQp95Vq0ONAHBDxjCjQ8QOazJMMM5MY4/export?format=csv"
    )
    try:
        df = pd.read_csv(sheet_csv_url)
    except Exception as e:
        st.error(f"❌ Error fetching Google Sheet: {e}")
        return []
    df.columns = ["Ad Text", "Ad Link"]
    ads = [
        f"{row['Ad Text']} <a href=\"{row['Ad Link']}\" target=\"_blank\">(link)</a>"
        for _, row in df.iterrows()
    ]
    return ads

def format_ads(ads):
    formatted_ads = []
    for ad in ads:
        ad_parts = ad.split('<a href="')
        ad_text = ad_parts[0].replace("IMPORTANT SPONSORED MESSAGE: ", "").strip()
        ad_url = ad_parts[1].split('" target="_blank">')[0] if len(ad_parts) > 1 else ""
        website = urlparse(ad_url).netloc if ad_url else "Unknown"
        formatted_ad = (
            f'<strong>IMPORTANT SPONSORED MESSAGE:</strong> {ad_text} '
            f'<a href="{ad_url}" target="_blank">{website}</a>'
        )
        formatted_ads.append(formatted_ad)
    return formatted_ads

def insert_data_into_template(scraped_headlines, ads):
    template_file = os.path.join(os.path.dirname(__file__), "texas_templates.html")
    try:
        with open(template_file, 'r', encoding='utf-8') as file:
            template = file.read()
    except Exception as e:
        st.error(f"❌ Error reading template file '{template_file}': {e}")
        return None

    ads = format_ads(ads)

    def format_section(section):
        return "".join(section) if section else ''

    random.shuffle(ads)
    ad_slots = list(scraped_headlines.keys())
    for i in range(min(len(ads), len(ad_slots))):
        scraped_headlines[ad_slots[i]].append(ads[i])

    for section, content in scraped_headlines.items():
        template = template.replace(f'{{{{{section}}}}}', format_section(content))

    est = pytz.timezone('US/Eastern')
    current_date = datetime.now(est).strftime("%B %d, %Y")
    template = template.replace("{{CURRENT_DATE}}", current_date)

    return template

# ---------------------------------------------------------
# Streamlit UI Setup
# ---------------------------------------------------------
st.title("Texas Report Headline & Ad Scraper")
st.write("Scrape latest headlines, insert ads, and build the HTML newsletter.")

# Session states
if "updated_html" not in st.session_state:
    st.session_state.updated_html = None
if "created_campaigns" not in st.session_state:
    st.session_state.created_campaigns = {}
if "campaign_names" not in st.session_state:
    st.session_state.campaign_names = {}

# Generate HTML Step
if st.button("Generate Updated HTML"):
    scraped_data = scrape_headlines()
    ads = get_ads()
    if "error" in scraped_data:
        st.error(scraped_data["error"])
    else:
        st.success("Headlines and ads fetched successfully!")
        updated_html = insert_data_into_template(scraped_data, ads)
        if updated_html:
            st.session_state.updated_html = updated_html
            st.success("HTML generated and stored in session.")

# Download button
if st.session_state.updated_html:
    st.download_button(
        label="Download Updated HTML",
        data=st.session_state.updated_html,
        file_name="Updated_Texas_Template.html",
        mime="text/html"
    )

st.subheader("BigMailer Campaign Setup")
subject_line = st.text_input("Subject Line", value="Texas Report - Enter Your Subject")
preview_text = st.text_input("Preview Text", value="Short preview text...")

st.markdown("#### Assign Sender Emails to Each List")
selected_senders = {}
for list_name in lists_config:
    chosen_sender = st.selectbox(
        f"Sender for {list_name}:",
        options=possible_senders,
        key=f"sender_{list_name}"
    )
    selected_senders[list_name] = chosen_sender

# -----------------------------------------------------------------
# Creating the campaigns
# -----------------------------------------------------------------
def create_bulk_campaign(list_name, list_id, sender, subject, preview, html):
    """
    Creates one bulk campaign on BigMailer, with from/reply objects as per docs.
    """
    url = f"https://api.bigmailer.io/v1/brands/{BIGMAILER_BRAND_ID}/bulk-campaigns"
    headers = {
        "X-API-Key": BIGMAILER_API_KEY,
        "Content-Type": "application/json"
    }

    # Custom campaign name, e.g. "May 10, 2025 Blast MAIN txreport.com"
    today_str = datetime.now().strftime("%B %d, %Y")
    sender_domain = sender.split("@")[-1] if "@" in sender else sender
    campaign_name = f"{today_str} Blast {list_name} {sender_domain}"

    payload = {
        "name": campaign_name,
        "subject": subject,
        "from": {
            "email": sender,
            "name": "TEXAS REPORT"
        },
        "reply_to": {
            "email": sender,
            "name": "TEXAS REPORT"
        },
        "preview": preview,
        "html": html,
        "track_opens": True,
        "track_clicks": True,
        "track_text_clicks": True,
        "list_ids": [list_id],
        "ready": False  # create now, send later
    }

    resp = requests.post(url, headers=headers, json=payload)
    if 200 <= resp.status_code < 300:
        data = resp.json()
        campaign_id = data.get("id")
        if campaign_id:
            st.session_state.campaign_names[campaign_id] = campaign_name
        return campaign_id
    else:
        st.error(f"❌ Error creating campaign for {list_name}")
        st.write(f"Status code: {resp.status_code}")
        st.write(f"Response text: {resp.text}")
        return None

def create_campaigns_for_all_lists():
    st.session_state.created_campaigns.clear()

    if not st.session_state.updated_html:
        st.error("No HTML to send. Please generate the email template first.")
        return

    for list_name, list_id in lists_config.items():
        sender = selected_senders[list_name]
        if sender == "None":
            st.warning(f"Skipping {list_name} (no sender).")
            continue

        campaign_id = create_bulk_campaign(
            list_name=list_name,
            list_id=list_id,
            sender=sender,
            subject=subject_line,
            preview=preview_text,
            html=st.session_state.updated_html
        )
        if campaign_id:
            st.success(f"✅ Created campaign {campaign_id} for {list_name}")
            st.session_state.created_campaigns[list_name] = campaign_id

# -----------------------------------------------------------------
# Sending the campaigns
# -----------------------------------------------------------------
def send_bulk_campaign(list_name, campaign_id):
    """
    Activates the previously created campaign (setting "ready"=true) via POST.
    """
    if campaign_id not in st.session_state.campaign_names:
        st.error("⚠ No saved name for this campaign – can't send.")
        return

    existing_name = st.session_state.campaign_names[campaign_id]

    url = f"https://api.bigmailer.io/v1/brands/{BIGMAILER_BRAND_ID}/bulk-campaigns/{campaign_id}"
    headers = {
        "X-API-Key": BIGMAILER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "name": existing_name,
        "ready": True
    }

    resp = requests.post(url, headers=headers, json=payload)
    if 200 <= resp.status_code < 300:
        st.success(f"✅ Campaign {campaign_id} for {list_name} is sending!")
    else:
        st.error(f"❌ Error sending campaign {campaign_id} for {list_name}")
        st.write(f"Status code: {resp.status_code}")
        st.write(f"Response text: {resp.text}")

def send_all_campaigns():
    """
    Re-POST all created campaigns with 'ready': True to start sending them.
    """
    if not st.session_state.created_campaigns:
        st.warning("No campaigns to send. Create campaigns first.")
        return

    for list_name, campaign_id in st.session_state.created_campaigns.items():
        send_bulk_campaign(list_name, campaign_id)

# -----------------------------------------------------------------
# Streamlit Buttons
# -----------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    if st.button("Create Campaigns"):
        create_campaigns_for_all_lists()
with col2:
    if st.button("Send Campaigns"):
        send_all_campaigns()
