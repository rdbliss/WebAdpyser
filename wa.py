#!/usr/bin/python3
"""CLI-frontend for WebAdvisor, OU's management software.
WebAdvisor is used in a lot of places (oasis.oglethorpe.edu, wa.gcccd.edu,
webadvisor.coastal.edu, etc.), and the WebAdvisor class is, for the most
part, compatible with all of them. Any specific sites will require code written
for them (different links, HTML, section names, etc.).

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
import os

def replace_url_query(url, query, value):
    """Replace/set the value of a given query in a url."""
    # urlparse returns a tuple that we can't modify.
    parse = list(uparse.urlparse(url))
    qdict = uparse.parse_qs(parse[4])
    qdict[query] = value
    parse[4] = uparse.urlencode(qdict, doseq=True)
    return uparse.urlunparse(parse)

def delete_url_query(url, query):
    """Delete a query from a given url. This is different from setting the value to ''."""
    parse = list(uparse.urlparse(url))
    qdict = uparse.parse_qs(parse[4])
    del qdict[query]
    parse[4] = uparse.urlencode(qdict, doseq=True)
    return uparse.urlunparse(parse)

def find_link(search, soup):
    """Find and return the first <a> tag's href element in `soup`."""
    link = soup.find("a", text=lambda t: search in t)
    return link.attrs["href"]

def parse_title_link(onclick):
    """Parse the onclick element of WA section title links for a query.
       It's a window.open call, and we only care about the first arg."""
    start_s = "window.open('"
    start = onclick.find(start_s)+len(start_s)
    end = onclick.find("'", start)
    return onclick[start:end]

def section_from_short_title(text):
    """Create a Section instance from a class's short title string.
    This is in the form of 'SUB-SEC-NUM (DIGITS) TITLE'."""
    section_info = text[:text.find(" ")]
    s = parse_section_string(section_info)
    text = text[len(section_info):].strip()
    s.title = text[text.find(" ")+1:]
    return s

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

    def section_string(self):
        return "%s-%s-%s" % (self.subject, self.number, self.section)

    def __iter__(self):
        # Column-wise order of the table.
        yield self.subject
        yield self.level
        yield self.number
        yield self.section
        # Now arbitrary.
        yield self.title
        yield self.faculty
        yield self.meeting
        yield self.credits
        yield self.capacity
        yield self.status

    def __str__(self):
        return " ".join([self.section_string(), self.title, self.faculty,
                         self.meeting, self.credits, self.status, self.capacity])

def contains(match):
    return lambda s: s and match in s

def grab_section_tags(r):
    """Grab section tags from the summary table."""
    soup = BeautifulSoup(r.content)

    titles = soup.find_all("a", {"id": contains("SEC_SHORT_TITLE")})
    stati = soup.find_all("p", {"id": contains("LIST_VAR1")})
    meetingi = soup.find_all("p", {"id": contains("SEC_MEETING_INFO")})
    faculti = soup.find_all("p", {"id": contains("SEC_FACULTY_INFO")})
    capaciti = soup.find_all("p", {"id": contains("LIST_VAR5")})
    crediti = soup.find_all("p", {"id": contains("SEC_MIN_CRED")})

    return zip(titles, stati, meetingi, faculti, capaciti, crediti)

def link_from_short_title(title_tag, r):
    """Parse the short title tag's attributes to find what it was redirecting to."""
    query = parse_title_link(title_tag.attrs["onclick"])
    url = r.url[:r.url.find("?")] + query
    url = delete_url_query(url, "CLONE")
    return url

def get_description_paragraph(soup):
    """Return the description paragraph from a class soup."""
    return soup.find("p", id="VAR3").text

def get_faculty_class_page(soup):
    """Return the faculty name(s) from a class page."""
    return soup.find("p", {"id": contains("LIST_VAR7")}).text

def grab_schedule_tags(r):
    """Grab tags from the class schedule table."""
    soup = BeautifulSoup(r.content)
    table = soup.find("table", {"summary": "Schedule"})

    titles = list(table.find_all("a", {"id": contains("LIST_VAR6")}))
    meetingi = list(table.find_all("p", {"id": contains("LIST_VAR12")}))
    crediti = list(table.find_all("p", {"id": contains("LIST_VAR8")}))
    start_dati = list(table.find_all("p", {"id": contains("DATE_LIST_VAR1")}))

    return zip(titles, meetingi, crediti, start_dati)

class WebAdvisor:
    """A class that attempts to encapsulate everything you could ever want to do in WebAdvisor."""
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
        self.last_request = self.get(url)

    def get(self, *args, **params):
        """Perform a GET request, using instance specific options.
        The `timeout` and `verify` kwargs will be ignored, but besides
        them, all arguments are passed DIRECTLY to self.session.get().
        """

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

    def detailed_from_short_title(self, title_tag, r):
        """Get a detailed paragraph from the short-title tag.
        Needs to GET a page, so in the WebAdvisor class."""
        url = link_from_short_title(title_tag, r)
        r = self.get(url)
        return get_description_paragraph(BeautifulSoup(r.content))

    def section_request(self, term="FA15R", *sections):
        """POST a section query. Assumes self.last_request is section page."""
        # TABLE.VARc_r, c column, r row.
        # Seems to break if only one section.
        max_rows = len(sections) if len(sections) > 1 else 2

        smax = str(max_rows)
        data = {"VAR1": term,
                "LIST.VAR1_MAX": smax,
                "LIST.VAR2_MAX": smax,
                "LIST.VAR3_MAX": smax,
                "LIST.VAR4_MAX": smax,
                "RETURN.URL": self.last_request.url,
                "LIST.VAR1_CONTROLLER": "LIST.VAR1",
                "LIST.VAR1_MEMBERS": "LIST.VAR1*LIST.VAR2*LIST.VAR3*LIST.VAR4"}

        for row, sec in zip(range(1, max_rows+1), sections):
            for col, item in zip(range(1, 5), sec):
                data["LIST.VAR{0}_{1}".format(col, row)] = item

        # Sometimes this is already set, but make sure.
        url = replace_url_query(self.last_request.url, "APP", "ST")
        return self.post(url, data=data)

    def grab_section_rows(self, r, detailed=False):
        """Grab the section information from the response of the section POST.
        If `detailed` is true, grab the course descriptions as well."""
        rets = []

        for tag_zip in grab_section_tags(r):
            title_tag = tag_zip[0]

            s = section_from_short_title(title_tag.text)
            text_list = [t.text for t in list(tag_zip[1:])]

            if detailed:
                s.detail = self.detailed_from_short_title(title_tag, r)

            s.status, s.meeting, s.faculty, s.capacity, s.credits = text_list
            rets.append(s)

        return rets

    def grab_schedule_rows(self, r, get_faculty=False):
        """Grab the section information from the response of the schedule POST.
        If `get_faculty` is true, grab the course faculty and description."""
        rets = []

        for tag_zip in grab_schedule_tags(r):
            title_tag = tag_zip[0]

            s = section_from_short_title(title_tag.text)
            text_list = [t.text for t in list(tag_zip[1:])]

            if get_faculty:
                # The faculty isn't listed on the course schedule,
                # so we have to go to the page to grab it.
                class_link = link_from_short_title(title_tag, r)
                soup = BeautifulSoup(self.get(class_link).content)
                s.faculty = get_faculty_class_page(soup)
                # We're here, let's just get it.
                s.detail = get_description_paragraph(soup)

            s.meeting, s.credits, s.start_date = text_list
            rets.append(s)

        return rets

    def login(self, username, password):
        """POST a login request.
        Assumes self.last_request is on the login page."""
        data = {"USER.NAME": username, "CURR.PWD": password,
                "RETURN.URL": self.last_request.url}
        r = self.post(self.last_request.url, data=data)
        soup = BeautifulSoup(r.content)
        if soup.find("div", {"class": "errorText"}):
            # Login failed for some reason.
            return None

        return r

    def get_class_schedule(self, term="FA15R"):
        """Grab the class schedule of an already-logged-in session.
        Assumes self.last_request is on the term-selection page."""
        data = {"RETURN.URL": self.last_request.url,
                "VAR4": term}
        return self.post(self.last_request.url, data=data)

# Validate options?
def parse_section_string(s):
    """Split a string SUB-NUM-SEC into a base Section.
    Does not currently (Mon Jul 20 2015) validate options."""
    return Section(*s.split("-"))

def add_filter_args(parser):
    """Add a series of 'standard' arguments to filter section results."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-g", "--greater", help="only report sections >= N",
                       metavar="N", type=int, default=0)
    group.add_argument("-l", "--less", help="only report sections <= N",
                       metavar="N", type=int, default=float("inf"))
    parser.add_argument("-f", "--faculty", help="get section faculty", action="store_true")
    parser.add_argument("-t", "--title", help="get section faculty", action="store_true")
    parser.add_argument("-m", "--meeting", help="get section meetings", action="store_true")
    parser.add_argument("-s", "--section", help="get section info", action="store_true")
    parser.add_argument("-c", "--capacity", help="get section capacity", action="store_true")
    parser.add_argument("-k", "--credits", help="get section credits", action="store_true")
    parser.add_argument("-v", "--verbose", help="get detailed section info (takes longer)",
                        action="store_true")
    parser.add_argument("-r", "--term", help="change term viewed", default="FA15R")
    parser.add_argument("-u", "--url", help="web advisor url; check wa.ini for list",
                        metavar="url", default="oasis.oglethorpe.edu")

    return parser

def print_with_args(args, sections):
    """Print a list of sections using the filters from add_filter_args()."""
    specific_print = False
    for section in sections:
        if (args.greater and int(section.number) < args.greater or
                args.less and int(section.number) > args.less):
            continue

        if args.section:
            specific_print = True
            print(section.section_string(), end=" ")
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
            print(section.section_string(), section.title, section.faculty, end="")
        if args.verbose:
            print()
            print(textwrap.fill(section.detail))
        print()

def get_script_dir():
    return os.path.dirname(os.path.realpath(sys.argv[0]))

def main():
    desc = "CLI-frontend for WebAdvisor, OU's student management server.\n"
    epilog = ("WebAdvisor sucks, so hard it's difficult to describe. "
              "If %s isn't working, try browsing oasis.oglethorpe.edu. "
              "It's probably broken, too.") % sys.argv[0]
    parser = argparse.ArgumentParser(description=desc, epilog=epilog)
    add_filter_args(parser)
    parser.add_argument("sec", nargs="+", help="string in form of SUB-NUM-SEC, i.e. MAT-241-001")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(os.path.join(get_script_dir(), "wa.ini"))

    conf_dict = config[args.url] if args.url in config else config["DEFAULT"]
    section_path = ast.literal_eval(conf_dict["to_section"])
    url = conf_dict["url"]
    verify = conf_dict.getboolean("verify")

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
    print_with_args(args, sections)

if __name__ == "__main__":
    main()
