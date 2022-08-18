import email
import streamlit as st
import databutton as db
import numpy as np
import pandas as pd
import requests as rq
from .tools import list_of_dates_to_date_ranges
import datetime
from email_validator import validate_email

DATA_KEY = 'user-subscriptions'

#month_lookup = {
    #'January':1,
    #'February':2,
    #'March':3,
    #'April':4,
    #'May':5,
    #'June':6,
    #'July':7,
    #'August':8,
    #'September':9,
    #'October':10,
    #'November':11,
    #'December':12
#}

@db.apps.streamlit('/apps/cabin-grabber',name="Cabin Grabber")
def cabin_grabber():
    st.title('Cabin Availability Grabber')
    st.markdown('''Get notified via email when a DNT cabin you care about is available.
    Travel and enjoy dat Norwegian nature 🇳🇴⛰ *#friluftslivsparadoxet*''')
    st.subheader('First, Grab a cab(in)')
    cabin_selection = st.text_input(label="Enter the cabin's Visbook URL (e.g. https://reservations.visbook.com/5471)")
    st.caption('Note: To get the Visbook URL for a cabin, find the cabin on UT.no and click Bestill overnatting')
    st.subheader('What dates are you interested in monitoring?')
    startDate = st.date_input(
        'From',
    )
    endDate = st.date_input(
        'To',
    )
    #st.subheader('Which months are you looking for availability in, good sir/mlady? 🎩')
    #months = st.multiselect('Select the month(s)', ['January','February','March','April','May','June','July','August','September','October','November','December'])
    st.caption('Note: You will get an email whenever your cabin has avaibility in the range you selected')
    st.subheader('Last step, can I haz your email?')
    email_input = st.text_input(label='Email address')
    email = None
    try:
        email = validate_email(email_input).email
    except:
        pass
    if st.button('Submit'):
        if email is not None:
            df = db.storage.dataframes.get(DATA_KEY)
            df = df.append({
                'email': email,
                'startDate': startDate,
                'endDate': endDate,
                #'months': months,
                'cabin_url': cabin_selection
            }, ignore_index=True)
            db.storage.dataframes.put(df, DATA_KEY)

            st.write('You are all set my friiiend')
            st.write('Emails about availablility at your selected cabin will go to {}'.format(email))
            st.write('Feel free to [buy me a ☕️](https://www.buymeacoffee.com/virals) if you love using Cabin Grabber to have the Norwegian trip of your dreams!')
        else:
            st.write("Your email is invalid. Sort it out bub.")

@db.jobs.repeat_every(seconds=60*60*24)
def check_availability():
    df = db.storage.dataframes.get(DATA_KEY)
    for index, row in df.iterrows():
        months = [month_lookup[month] for month in row.months]
        locationId = row['cabin_url'].split('/')[-1]
        response = rq.get(f"https://ws.visbook.com/8/api/{locationId}/webproducts")
        info = response.json()
        if 'error' in info:
            continue
        hytter = []
        for hytte in info:
            hytter.append({
                'id': hytte['webProductId'],
                'name': hytte['unitName']
            })

        summary = []
        for hytte in hytter:
            for month in months:
                url = f"https://ws.visbook.com/8/api/{locationId}/availability/{hytte['id']}/2022-{month}"
                response = rq.get(url)
                tories = response.json()
                if 'error' in tories:
                    continue
                items_list = tories['items']
                available_days = []
                for item in items_list:
                    date = item['date']
                    webProducts = item['webProducts']
                    if len(webProducts) > 0:
                        product = webProducts[0]
                        if 'availability' in product:
                            is_available = product['availability']['available']
                            if is_available:
                                available_days.append(date)
            
            available_ranges = list_of_dates_to_date_ranges(available_days)
            summary.append({
                "name": hytte["name"],
                "id": hytte["id"],
                "available_days": available_ranges,
            })
        df = pd.DataFrame(summary)
        html = df.to_html()
        db.notify.email(
            to=[row.email],
            subject="Fresh results from cabin grabber",
            content_html=html
        )