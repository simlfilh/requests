from supabase import create_client
import pandas as pd

SUPABASE_URL = "https://ptdxlveqzmrrdlbtuxck.supabase.co"  # Вставь свой URL
SUPABASE_KEY = "sb_publishable_JlbWpuP2kvzMdOpyDwIOzg_XCI3VWNv"  # Вставь свой ключ

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def save_request(data):
    supabase = get_supabase()
    supabase.table('requests').insert({
        "date": data["date"],
        "time": data["time"],
        "fio": data["fio"],
        "room": data["room"],
        "type": data["type"],
        "description": data["description"],
        "status": "Новая"
    }).execute()

def load_requests():
    supabase = get_supabase()
    response = supabase.table('requests').select('*').order('id', desc=False).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame()

def update_status(request_id, new_status):
    supabase = get_supabase()
    supabase.table('requests').update({'status': new_status}).eq('id', request_id).execute()