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

# Returns to main page?
# Just a guess: SS query is getting in the way.
web.post(web.last_request.url, data={ "RETURN.URL": web.last_request.url, "VAR4": "FA15R"})
soup = BeautifulSoup(web.last_request.content)
print(soup.text)
