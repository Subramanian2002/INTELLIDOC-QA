from supabase import create_client
import requests
from io import BytesIO
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


supabase = create_client(SUPABASE_URL,SUPABASE_KEY)

def upload_file_to_supabase(file,chat_id):
    file_bytes = file.read()
    file_path = f"{chat_id}/{file.name}"

    supabase.storage.from_("documents").upload(
    path=file_path,
    file=file_bytes,
    file_options={
        "metadata": {
            "owner": str(st.session_state.user_id)
        }
    }
)
    # get public url
    public_url = supabase.storage.from_("documents").get_public_url(file_path)

    return public_url

def download_file_from_url(url):
    response = requests.get(url)

    if response.status_code == 200:
        return BytesIO(response.content)
    else:
        return None