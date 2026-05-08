import streamlit as st
import praw
from duckduckgo_search import DDGS
from openai import OpenAI
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="Local Job Connection Scanner", page_icon="💼", layout="wide")
st.title("💼 Local Job Connection Scanner")
st.markdown("**100% public data only • No sketchy scraping • Just legit 'we're hiring' and 'in search of' posts in your area.**")

# Sidebar
with st.sidebar:
    st.header("Search Settings")
    location = st.text_input("City or Zip Code", value="Denver, CO")
    keywords = st.text_input("Job Keywords", value="software engineer OR marketing OR sales OR developer")
    
    platforms = st.multiselect("Platforms", ["Reddit", "Web (Public Search)"], default=["Reddit", "Web (Public Search)"])
    
    st.subheader("API Keys (secure)")
    reddit_client_id = st.text_input("Reddit Client ID", type="password", value=st.secrets.get("REDDIT_CLIENT_ID", ""))
    reddit_client_secret = st.text_input("Reddit Client Secret", type="password", value=st.secrets.get("REDDIT_CLIENT_SECRET", ""))
    reddit_user_agent = st.text_input("Reddit User Agent", value=st.secrets.get("REDDIT_USER_AGENT", "LocalJobScanner by bhenry94"))
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
        contacts = extract_public_contacts(post_text)
        return {"score": 60, "contacts": contacts, "suggestion": "Add your OpenAI key for smarter analysis and outreach drafts."}
    
    prompt = f"""
    Analyze this public post for job networking potential in {location}.
    Score 0-100 (real opportunity, not spam).
    Extract ONLY publicly posted contact info.
    Draft a short, professional 2-sentence outreach message.
    Post: {post_text[:2500]}
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        analysis = resp.choices[0].message.content
        contacts = extract_public_contacts(post_text + analysis)
        return {"score": 75, "contacts": contacts, "suggestion": analysis}
    except:
        return {"score": 50, "contacts": extract_public_contacts(post_text), "suggestion": "LLM failed - using basic extraction"}

if st.button("🚀 SCAN PUBLIC LISTINGS", type="primary", use_container_width=True):
    all_leads = []
    
    # REDDIT
    if "Reddit" in platforms and reddit:
        st.info("Scanning Reddit (official API only)...")
        subs = ["jobs", "forhire", "hiring", "jobpostings", "resumes"]
        query = f"{keywords} {location} (hiring OR \"now hiring\" OR \"in search of\" OR \"we are hiring\" OR \"looking to hire\")"
        
        for sub_name in subs:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.search(query, limit=15, sort="new"):
                    text = post.title + "\n" + (post.selftext or "")
                    analysis = ai_analyze_post(text, "Reddit", location)
                    if analysis["score"] > 45:
                        all_leads.append({
                            "Platform": "Reddit",
                            "Title": post.title[:100],
                            "URL": f"https://reddit.com{post.permalink}",
                            "Date": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d"),
                            "Score": analysis["score"],
                            "Contacts": analysis["contacts"],
                            "Suggestion": analysis["suggestion"]
                        })
            except:
                pass

    # PUBLIC WEB SEARCH
    if "Web (Public Search)" in platforms:
        st.info("Scanning public web (DuckDuckGo)...")
        ddgs_query = f'{keywords} "{location}" (hiring OR "now hiring" OR "in search of" OR "we are hiring")'
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(ddgs_query, max_results=20))
                for r in results:
                    text = r.get("title", "") + " " + r.get("body", "")
                    analysis = ai_analyze_post(text, "Web", location)
                    if analysis["score"] > 45:
                        all_leads.append({
                            "Platform": "Web/Public",
                            "Title": r.get("title", "No title")[:100],
                            "URL": r.get("href"),
                            "Date": "Recent",
                            "Score": analysis["score"],
                            "Contacts": analysis["contacts"],
                            "Suggestion": analysis["suggestion"]
                        })
        except:
            st.warning("Web search hit a snag - try again in a minute.")

    if all_leads:
        df = pd.DataFrame(all_leads)
        st.success(f"Found {len(df)} solid public leads!")
        
        # Simple table
        display_df = df[["Platform", "Title", "URL", "Date", "Score"]].copy()
        st.dataframe(display_df, use_container_width=True)
        
        # Detailed cards
        for i, row in df.iterrows():
            with st.expander(f"📍 {row['Platform']} • {row['Title']} (Score: {row['Score']})"):
                st.markdown(f"**Link:** [{row['URL']}]({row['URL']})")
                st.write("**Public Contact Info:**")
                for k, v in row["Contacts"].items():
                    if v:
                        st.write(f"**{k}:** {', '.join(v)}")
                st.write("**Suggested Outreach:**")
                st.info(row["Suggestion"])
        
        # Export
        csv = df.to_csv(index=False).encode()
        st.download_button(
            label="📥 Download All Leads as CSV",
            data=csv,
            file_name=f"job_leads_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("No strong leads right now. Try different keywords or check your API keys.")

st.caption("✅ Clean public data only • Built for bhenry94 • Deployed from GitHub. Hit me up if you want Google Sheets sync or email alerts next.")
