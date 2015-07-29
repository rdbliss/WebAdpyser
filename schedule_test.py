#!/usr/bin/python3
import wa
from bs4 import BeautifulSoup

user = input("user: ")
password = input("password: ")

web = wa.WebAdvisor("https://oasis.oglethorpe.edu")

web.follow_link("Log In")
soup = BeautifulSoup(web.last_request.content)
web.login(user, password)
soup = BeautifulSoup(web.last_request.content)
print(soup.text)

web.follow_link("for Students")
web.follow_link("My class")
soup = BeautifulSoup(web.last_request.content)

web.get_class_schedule("FA15R")

print("Schedule for %s:" % user)
for section in web.grab_schedule_rows(web.last_request, True):
    print(section)
    if section.detail:
        print(section.detail)
