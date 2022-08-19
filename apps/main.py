import email
import streamlit as st
import databutton as db
import numpy as np
import pandas as pd
import requests as rq
from .tools import get_availability
import datetime
from email_validator import validate_email

DATA_KEY = 'user-subscriptions'


@db.apps.streamlit('/apps/cabin-grabber',name="Cabin Grabber")
def cabin_grabber():
    st.title('Cabin Availability Grabber')
    st.markdown('''Get notified via email when a DNT cabin you care about is available.
    Travel and enjoy dat Norwegian nature 🇳🇴⛰ *#friluftslivsparadoxet*''')
    st.subheader('First, Grab a cab(in)')
    cabin_selection = st.text_input(label="Enter the cabin's Visbook URL (e.g. https://reservations.visbook.com/5471)")
    st.caption('Note: To get the Visbook URL for a cabin, find the cabin on UT.no and click Bestill overnatting')
    st.subheader('What dates are you interested in monitoring?')

    startDate = st.date_input('From', min_value=datetime.datetime.today())
    endDate = st.date_input('To', min_value=datetime.datetime.today())
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
        start_date = row['startDate']
        end_date   = row['endDate']
        locationId = row['cabin_url'].split('/')[-1]
        
        summary = get_availability(locationId, start_date, end_date)
        df = pd.DataFrame(summary)
        html = df.to_html()
        db.notify.email(
            to=[row.email],
            subject="Fresh results from cabin grabber",
            content_html=html
        )