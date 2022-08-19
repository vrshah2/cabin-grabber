import base64
import pandas as pd
import requests as rq
import databutton as db
from datetime import datetime, date
#
#  *** CONVERT LIST OF DATES TO LIST OF DATE RANGES ***
#

def get_range_string(t_from, t_to):
    str_from = str(t_from.day) + '.'+ str(t_from.month)
    str_to   = str(t_to.day) + '.'+ str(t_to.month)
    
    return str_from + '-' + str_to


def list_of_dates_to_date_ranges(data):
    dg = pd.to_datetime(data).reset_index(drop=True)
    ranges = []
    fra = 0
    for ix in range(1, len(dg)):
        to = ix-1
        if((dg[ix] - dg[ix-1])!=pd.Timedelta('1 days')):
            ranges.append(get_range_string(dg[fra], dg[to]))
            fra = ix

    ranges.append(get_range_string(dg[fra], dg[to+1]))
    
    return ranges


def filter_list_of_dates(datelist, start_date, end_date):
    dg = pd.Series([pd.to_datetime(s).tz_localize(None) for s in datelist])
    start = pd.to_datetime(start_date).tz_localize(None)
    end   = pd.to_datetime(end_date).tz_localize(None)
    

    return dg[((dg >= start) & (dg <= end))]




def get_months(start, end):
    month_start = start.month
    month_end   = end.month

    return list(range(month_start, month_end+1))
    


#
#  *** Ask for availability of a cabin
#
def get_list_of_cabin_options(locationId):
    response = rq.get(f"https://ws.visbook.com/8/api/{locationId}/webproducts")
    info = response.json()
    if 'error' in info:
        return -1

    
    hytter = []
    for hytte in info:
        hytter.append({
            'id': hytte['webProductId'],
            'name': hytte['unitName']
        })

    return hytter






def get_availability(locationId, start_date, end_date):
    hytter = get_list_of_cabin_options(locationId)
    months = get_months(start_date, end_date)

    summary = []
    for hytte in hytter:
            available_days = []
            for month in months:
                url = f"https://ws.visbook.com/8/api/{locationId}/availability/{hytte['id']}/2022-{month}"
                response = rq.get(url)
                tories = response.json()
                if 'error' in tories:
                    continue
                items_list = tories['items']
                for item in items_list:
                    date = item['date']
                    webProducts = item['webProducts']
                    if len(webProducts) > 0:
                        product = webProducts[0]
                        if 'availability' in product:
                            is_available = product['availability']['available']
                            if is_available:
                                available_days.append(date)

            available_days = filter_list_of_dates(available_days, start_date, end_date)
            available_ranges = list_of_dates_to_date_ranges(available_days)
            summary.append({
                "name": hytte["name"],
                "id": hytte["id"],
                "available_days": available_ranges
            })

    return summary 


#
# Simply not-that-secure encryption :) 
#
def encode(key, string):
    encoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(ord(string[i]) + ord(key_c) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = "".join(encoded_chars)
    print(encoded_string)
    return base64.urlsafe_b64encode(encoded_string.encode())



def dencode(key, string):
    string = base64.urlsafe_b64decode(string).decode()
    dencoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        dencoded_c = chr(ord(string[i]) - ord(key_c) % 256)
        dencoded_chars.append(dencoded_c)
    dencoded_string = "".join(dencoded_chars)
    return dencoded_string



def encrypt_message(string):
    key = db.secrets.get('cryptokey')
    return encode(key, string)



def decrypt_message(string):
    key = db.secrets.get('cryptokey')
    return dencode(key, string)