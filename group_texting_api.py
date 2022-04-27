import requests
import json

base_url = 'https://app.grouptexting.com/sending/messages?format=JSON'


def send_message(message_body, sender_list, subject=None):
    data = {
        'User': '',  # (Required) Your Group Texting username
        'Password': '',  # (Required) Your Group Texting password
        'PhoneNumbers': sender_list,  # (Optional) Array of 10 digit phone number to send message to
        # 'Groups': '',  # (Optional) Groups to send message to; if you don't include groups, you must specify phone numbers to send message to
        # 'Subject': '',  # (Optional) The subject of your message up to 13 characters
        'Message': message_body,  #(Required) The body of your message
        'StampToSend': ''  # (Optional) Time to send a scheduled message (should be a Unix timestamp)
    }
