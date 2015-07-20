#!/usr/bin/python3
"""CLI-frontend for WebAdvisor, OU's management software.
WebAdvisor is used in a lot of places (oasis.oglethorpe.edu, wa.gcccd.edu,
webadvisor.coastal.edu, etc.), and the WebAdvisor class is, for the most
part, compatible with all of them. Any specific sites will require code written
for them (different links, HTML, section names, etc.).

TODO: Test more sites, abstract if possible.
      Grab list of section options from section page (VAR1).
      Speed up; 2.8 seconds is a long time:
        Most of it is SSL, but the rest is bs4.

      See "wa.ini" for site-agnostics.
"""

from urllib import parse as uparse
from bs4 import BeautifulSoup
import configparser
import textwrap
import requests
import argparse
import sys
import ast

def replace_url_query(url, query, value):
    # urlparse returns a tuple that we can't modify.
    parse = list(uparse.urlparse(url))
    qdict = uparse.parse_qs(parse[4])
    qdict[query] = value
    parse[4] = uparse.urlencode(qdict, doseq=True)
    return uparse.urlunparse(parse)

def delete_url_query(url, query):
    parse = list(uparse.urlparse(url))
    qdict = uparse.parse_qs(parse[4])
    del qdict[query]
    parse[4] = uparse.urlencode(qdict, doseq=True)
    return uparse.urlunparse(parse)

def find_link(search, soup):
    link = soup.find("a", text=lambda t: search in t)
    return link.attrs["href"]

def parse_title_link(onclick):
    """Parse the onclick element of WA section title links for a query.
       It's a window.open call, and we only care about the first arg."""
    start_s = "window.open('"
    start = onclick.find(start_s)+len(start_s)
    end = onclick.find("'", start)
    return onclick[start:end]

class Section:
    def __init__(self, subject="", number="", section="", level="", faculty="",
                    title="", meeting="", capacity="", credits="", status=""):
        self.subject = subject
        self.level = level
        self.number = number
        self.faculty = faculty
        self.title = title
        self.meeting = meeting
        self.capacity = capacity
        self.credits = credits
        self.status = status

        try:
            self.section = "%03d" % int(section)
        except ValueError:
            self.section = ""

        try:
            # Sometimes numbers have things tacked on, i.e. PHY-101L for lab.
            # XXX: Thus far I've only seen 3-digits.
            self.number = "%03d" % int(number[:3])
        except ValueError:
            self.number = ""

    def __iter__(self):
        # Column-wise order of the table.
        yield self.subject; yield self.level
        yield self.number; yield self.section
        # Now arbitrary.
        yield self.title; yield self.faculty
        yield self.meeting; yield self.credits
        yield self.capacity; yield self.status

    def __str__(self):
        return "%s-%s-%s %s %s %s %s %s %s" % (self.subject, self.number,
        self.section, self.title, self.faculty, self.meeting, self.credits,
        self.status, self.capacity)

def grab_section_tags(r):
    soup = BeautifulSoup(r.content)
    def contains(match):
        return lambda s: s and match in s

    titles = [t for t in soup.find_all("a", {"id": contains("SEC_SHORT_TITLE")})]
    stati = [t for t in soup.find_all("p", {"id": contains("LIST_VAR1")})]
    meetingi = [t for t in soup.find_all("p", {"id": contains("SEC_MEETING_INFO")})]
    faculti = [t for t in soup.find_all("p", {"id": contains("SEC_FACULTY_INFO")})]
    capaciti = [t for t in soup.find_all("p", {"id": contains("LIST_VAR5")})]
    crediti = [t for t in soup.find_all("p", {"id": contains("SEC_MIN_CRED")})]

    return zip(titles, stati, meetingi, faculti, capaciti, crediti)

def get_description_paragraph(r):
    soup = BeautifulSoup(r.content)
    return soup.find("p", id="VAR3").text

class WebAdvisor:
    def __init__(self, url, verify=True, timeout=6):
        self.session = requests.Session()
        self.verify = verify
        self.timeout = timeout
        r = self.get(url)

        # "TOKENIDX=" sets LASTTOKEN.
        r = self.get(r.url, params={"TOKENIDX": ""})
        self.token = r.cookies["LASTTOKEN"]

        # URL's accumlate; make sure the blank doesn't stick around.
        url = replace_url_query(r.url, "TOKENIDX", self.token)

        # Send token cookie/parameter; now at main page with proper links.
        r = self.get(url)

    def get(self, *args, **params):
        params["timeout"] = self.timeout
        params["verify"] = self.verify

        self.last_request = self.session.get(*args, **params)
        return self.last_request

    def post(self, *args, **params):
        self.last_request = self.session.post(*args, **params)
        return self.last_request

    def follow_link(self, text):
        """Search for and attempt to follow the first
            link in the last response."""
        soup = BeautifulSoup(self.last_request.content)
        link = find_link(text, soup)
        return self.get(link)

    def section_request(self, term="FA15R", *sections):
        """POST a section query. Assumes self.last_request is section page."""
        # TABLE.VARc_r, c column, r row.
        # Seems to break if only one section.
        max = len(sections) if len(sections) > 1 else 2

        smax = str(max)
        data={ "VAR1": term
             , "LIST.VAR1_MAX": smax
             , "LIST.VAR2_MAX": smax
             , "LIST.VAR3_MAX": smax
             , "LIST.VAR4_MAX": smax
             , "RETURN.URL": self.last_request.url
             , "LIST.VAR1_CONTROLLER": "LIST.VAR1"
             , "LIST.VAR1_MEMBERS": "LIST.VAR1*LIST.VAR2*LIST.VAR3*LIST.VAR4"}

        for row,sec in zip(range(1,max+1), sections):
            for col,item in zip(range(1,5), sec):
                data["LIST.VAR{0}_{1}".format(col, row)] = item

        # Sometimes this is already set, but make sure.
        url = replace_url_query(self.last_request.url, "APP", "ST")
        return self.post(url, data=data)

    def grab_section_rows(self, r, detailed=False):
        """Grab the section information from the response of the section POST.
        If `detailed` is true, grab the course descriptions as well."""
        rets = []

        for zipper in grab_section_tags(r):
            title_tag = zipper[0]

            title = title_tag.text
            section_info = title[:title.find(" ")]
            s = parse_section_string(section_info)
            title = title[len(section_info):].strip()
            s.title = title[title.find(" ")+1:]

            text_list = [t.text for t in list(zipper[1:])]

            if detailed:
                query = parse_title_link(title_tag.attrs["onclick"])
                url = r.url[:r.url.find("?")] + query
                url = delete_url_query(url, "CLONE")
                s.detail = get_description_paragraph(self.get(url))

            s.status, s.meeting, s.faculty, s.capacity, s.credits = text_list
            rets.append(s)

        return rets

    def login(self, username, password):
        """POST a login request.
        Assumes self.last_request is on the login page."""
        data = { "USER.NAME": username
               , "CURR.PWD": password
               , "RETURN.URL": self.last_request.url}
        return self.post(self.last_request.url, data=data)

# Validate options?
def parse_section_string(s):
    """Split a string SUB-NUM-SEC into a base Section.
    Does not currently (Mon Jul 20 2015) validate options."""
    return Section(*s.split("-"))

if __name__ == "__main__":
    desc = "CLI-frontend for WebAdvisor, OU's student management server.\n"
    epilog = ("WebAdvisor sucks, so hard it's difficult to describe. "
              "If %s isn't working, try browsing oasis.oglethorpe.edu. "
              "It's probably broken, too.") % sys.argv[0]

    parser = argparse.ArgumentParser(description=desc, epilog=epilog)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-g", "--greater", help="only report sections >= N", metavar="N", type=int, default=0)
    group.add_argument("-l", "--less", help="only report sections <= N", metavar="N", type=int, default=float("inf"))
    parser.add_argument("sec", nargs="+", help="string in form of SUB-NUM-SEC, i.e. MAT-241-001")
    parser.add_argument("-f", "--faculty", help="get section faculty", action="store_true")
    parser.add_argument("-t", "--title", help="get section faculty", action="store_true")
    parser.add_argument("-m", "--meeting", help="get section meetings", action="store_true")
    parser.add_argument("-s", "--section", help="get section info", action="store_true")
    parser.add_argument("-c", "--capacity", help="get section capacity", action="store_true")
    parser.add_argument("-k", "--credits", help="get section credits", action="store_true")
    parser.add_argument("-v", "--verbose", help="get detailed section info (takes considerably longer)", action="store_true")
    parser.add_argument("-r", "--term", help="change term viewed", default="FA15R")
    parser.add_argument("-u", "--url", metavar="url", help="web advisor url; check wa.ini for list", default="oasis.oglethorpe.edu")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read("wa.ini")

    if args.url in config:
        section_path = ast.literal_eval(config[args.url]["to_section"])
        url = config[args.url]["url"]
        verify = config[args.url].getboolean("verify")
    else:
        # Section URL, not connection URL.
        url = config["DEFAULT"]["url"]
        section_path = ast.literal_eval(config[url]["to_section"])
        url = config[url]["url"]
        verify = config["DEFAULT"].getboolean("verify")

    # Suppress SSL warnings.
    if not verify:
        exceptions = requests.packages.urllib3.exceptions.SecurityWarning
        requests.packages.urllib3.disable_warnings(category=exceptions)

    wa = WebAdvisor(url, verify)
    for link in section_path:
        wa.follow_link(link)

    sections = [parse_section_string(s) for s in args.sec]
    r = wa.section_request(args.term, *sections)
    sections = wa.grab_section_rows(r, args.verbose)

    specific_print = False
    for section in sections:
        if ((args.greater and int(section.number) < args.greater) or
            (args.less    and int(section.number) > args.less)):
            continue

        if args.section:
            specific_print = True
            print("%s-%s-%s" % (section.subject, section.number,
                                section.section), end=" ")
        if args.title:
            specific_print = True
            print(section.title, end=" ")
        if args.faculty:
            specific_print = True
            print(section.faculty, end=" ")
        if args.meeting:
            specific_print = True
            print(section.meeting, end=" ")
        if args.credits:
            specific_print = True
            print(section.credits, end=" ")
        if args.capacity:
            specific_print = True
            print(section.capacity, end=" ")
        if not specific_print:
            print(section, end=" ")
        if args.verbose:
            print()
            print(textwrap.fill(section.detail))

        print()
