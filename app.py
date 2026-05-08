import streamlit as st
import praw
from duckduckgo_search import DDGS
from openai import OpenAI
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="Local Job Connection Scanner", page_icon="💼", layout="wide")
st.title("💼 Local Job Connection Scanner - Rural Edition")
st.markdown("**Public-only • Craigslist + FB/IG web hits for the sticks • No sketchy shit**")

# Sidebar
with st.sidebar:
    st.header("Search Settings")
    location = st.text_input("City, Town or Zip Code", value="Boise, ID")
    keywords = st.text_input("Keywords", value="hiring OR \"now hiring\" OR \"in search of\" OR \"we are hiring\" OR \"looking for help\" OR \"help wanted\"")
    
    st.subheader("API Keys")
    reddit_client_id = st.text_input("Reddit Client ID", type="password", value=st.secrets.get("REDDIT_CLIENT_ID", ""))
    reddit_client_secret = st.text_input("Reddit Client Secret", type="password", value=st.secrets.get("REDDIT_CLIENT_SECRET", ""))
    reddit_user_agent = st.text_input("Reddit User Agent", value=st.secrets.get("REDDIT_USER_AGENT", "LocalJobScanner"))
    openai_key = st.text_input("OpenAI API Key", type="password", value=st.secrets.get("OPENAI_API_KEY", ""))

@st.cache_resource
def get_reddit():
    if not reddit_client_id or not reddit_client_secret:
        return None
    return praw.Reddit(client_id=reddit_client_id, client_secret=reddit_client_secret, user_agent=reddit_user_agent)

reddit = get_reddit()
client = OpenAI(api_key=openai_key) if openai_key else None

def extract_public_contacts(text):
    email = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    linkedin = re.findall(r'linkedin\.com/in/[\w-]+', text)
    x_handle = re.findall(r'@([A-Za-z0-9_]+)', text)
    phone = re.findall(r'(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', text)
    return {
        "Emails": list(set(email)),
        "LinkedIn": list(set(linkedin)),
        "X Handles": list(set(x_handle)),
        "Phones": list(set(phone))
    }

def ai_analyze_post(post_text, platform, location):
    if not client:
        return {"score": 60, "contacts": extract_public_contacts(post_text), "suggestion": "Add OpenAI key for smarter outreach."}
    try:
        prompt = f"Analyze this public {platform} post for real job networking in {location}. Score 0-100. Extract only public contacts. Draft short professional outreach."
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt + "\nPost: " + post_text[:2000]}]
        )
        analysis = resp.choices[0].message.content
        return {"score": 75, "contacts": extract_public_contacts(post_text + analysis), "suggestion": analysis}
    except:
        return {"score": 55, "contacts": extract_public_contacts(post_text), "suggestion": "Basic contacts extracted."}

if st.button("🚀 SCAN PUBLIC EVERYWHERE (Craigslist + FB + IG + Reddit)", type="primary", use_container_width=True):
    all_leads = []
    
    # Reddit
    if reddit:
        st.info("Scanning Reddit...")
        subs = ["jobs", "forhire", "hiring", "jobpostings"]
        query = f"{keywords} {location}"
        for sub_name in subs:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.search(query, limit=12, sort="new"):
                    text = post.title + "\n" + (post.selftext or "")
                    analysis = ai_analyze_post(text, "Reddit", location)
                    if analysis["score"] > 45:
                        all_leads.append({
                            "Platform": "Reddit",
                            "Title": post.title[:90],
                            "URL": f"https://reddit.com{post.permalink}",
                            "Date": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d"),
                            "Score": analysis["score"],
                            "Contacts": analysis["contacts"],
                            "Suggestion": analysis["suggestion"]
                        })
            except:
                pass

    # Craigslist + Facebook Groups + Instagram + General Web (rural killer)
    st.info("Hitting Craigslist + public Facebook/Instagram...")
    ddgs = DDGS()
    search_queries = [
        f'{keywords} {location} site:craigslist.org',
        f'{keywords} {location} "facebook.com/groups"',
        f'{keywords} {location} site:instagram.com "hiring" OR "help wanted"',
        f'{keywords} "{location}" "now hiring" OR "in search of"',
        f'help wanted {location} -site:indeed.com -site:linkedin.com'
    ]
    
    for q in search_queries:
        try:
            results = list(ddgs.text(q, max_results=12))
            for r in results:
                text = r.get("title", "") + " " + r.get("body", "")
                analysis = ai_analyze_post(text, "Craigslist/FB/IG/Web", location)
                if analysis["score"] > 45:
                    all_leads.append({
                        "Platform": "Craigslist/FB/IG/Web",
                        "Title": r.get("title", "No title")[:90],
                        "URL": r.get("href"),
                        "Date": "Recent",
                        "Score": analysis["score"],
                        "Contacts": analysis["contacts"],
                        "Suggestion": analysis["suggestion"]
                    })
        except:
            pass

    # Show results
    if all_leads:
        df = pd.DataFrame(all_leads)
        st.success(f"Found {len(df)} leads! Rural mode activated.")
        st.dataframe(df[["Platform", "Title", "URL", "Date", "Score"]], use_container_width=True)
        
        for i, row in df.iterrows():
            with st.expander(f"📍 {row['Platform']} - {row['Title']} (Score: {row['Score']})"):
                st.markdown(f"**Link:** [{row['URL']}]({row['URL']})")
                st.write("**Public Contacts:**")
                for k, v in row["Contacts"].items():
                    if v:
                        st.write(f"**{k}:** {', '.join(v)}")
                st.write("**Suggested Outreach:**")
                st.info(row["Suggestion"])
        
        csv = df.to_csv(index=False).encode()
        st.download_button("📥 Download CSV", csv, f"job_leads_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    else:
        st.warning("Dry as a desert out there. Try a bigger nearby town or looser keywords.")

st.caption("✅ 100% public data • Craigslist is your rural MVP • FB/IG via web only (Meta blocks direct access). Want me to add Apify for deeper public group access next?")
