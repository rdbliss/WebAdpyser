#!/usr/bin/python3
import wa
from bs4 import BeautifulSoup
from getpass import getpass

parser = wa.create_parser()
args = parser.parse_args()

user = input("user: ")
password = getpass("pass: ")

web = wa.WebAdvisor("https://oasis.oglethorpe.edu")
web.follow_link("Log In")
web.login(user, password)
web.follow_link("for Students")
web.follow_link("My class")
web.get_class_schedule("FA15R")

print("Schedule for %s:" % user)
wa.print_with_args(args, web.grab_schedule_rows(web.last_request, args.verbose))
