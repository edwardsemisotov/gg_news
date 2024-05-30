from instagrapi import Client

cl = Client()
cl.login('warsaw.infocore.news', '3jjXrh@@w@-BdMX')
media = cl.photo_upload(path="cat.jpeg", caption="srk is love")