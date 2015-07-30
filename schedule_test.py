#!/usr/bin/python3
import wa
from bs4 import BeautifulSoup
from getpass import getpass
import argparse
import sys

desc = "Grab a course schedule from OASIS."
epilog=("Grabbing schedules is a little slower than grabbing course listings "
        "because to get all of the 'base' information, we have to GET the "
        "whole class page, not just the table summarizing the info.")

parser = argparse.ArgumentParser(description=desc, epilog=epilog)
wa.add_filter_args(parser)
parser.add_argument("user", nargs="?", help="username to use at OASIS")
args = parser.parse_args()

if args.user:
    user = args.user
else:
    print("user: ", file=sys.stderr, end="")
    user = input()
password = getpass("pass: ", stream=sys.stderr)

web = wa.WebAdvisor("https://oasis.oglethorpe.edu")
web.follow_link("Log In")
print("This may take a few seconds...", file=sys.stderr)
print("Logging in...", file=sys.stderr)
web.login(user, password)
web.follow_link("for Students")
web.follow_link("My class")
web.get_class_schedule("FA15R")
print("Grabbing schedule...", file=sys.stderr)
wa.print_with_args(args, web.grab_schedule_rows(web.last_request, args.verbose))
