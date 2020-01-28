from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import re
import json
import requests
import sys
import os
import asyncio
import jinja2
import argparse
from concurrent.futures import ThreadPoolExecutor

parser = argparse.ArgumentParser(
    description=
    "Instagram location data gathering tool.  Usage: python3 InstaLocTrack.py -t <target_account>",
    prog="InstaLocTrack")

parser.add_argument(
    "-t",
    "--target",
    dest="target_account",
    help="Instagram profile to investigate",
)

parser.add_argument(
    "-l",
    "--login",
    dest="login",
    help=
    "Instagram profile to connect to, in order to access the instagram posts of the target account",
)

parser.add_argument(
    "-p",
    "--password",
    dest="password",
    help="Password of the Instagram profile to connect to",
)

parser.add_argument(
    "-v",
    "--visual",
    action='store_true',
    help="Spawns Chromium GUI, otherwise Chromium is headless",
)

args = parser.parse_args()

special_chars = {
    "u00c0": "À",
    "u00c1": "Á",
    "u00c2": "Â",
    "u00c3": "Ã",
    "u00c4": "Ä",
    "u00c5": "Å",
    "u00c6": "Æ",
    "u00c7": "Ç",
    "u00c8": "È",
    "u00c9": "É",
    "u00ca": "Ê",
    "u00cb": "Ë",
    "u00cc": "Ì",
    "u00cd": "Í",
    "u00ce": "Î",
    "u00cf": "Ï",
    "u00d1": "Ñ",
    "u00d2": "Ò",
    "u00d3": "Ó",
    "u00d4": "Ô",
    "u00d5": "Õ",
    "u00d6": "Ö",
    "u00d8": "Ø",
    "u00d9": "Ù",
    "u00da": "Ú",
    "u00db": "Û",
    "u00dc": "Ü",
    "u00dd": "Ý",
    "u00df": "ß",
    "u00e0": "à",
    "u00e1": "á",
    "u00e2": "â",
    "u00e3": "ã",
    "u00e4": "ä",
    "u00e5": "å",
    "u00e6": "æ",
    "u00e7": "ç",
    "u00e8": "è",
    "u00e9": "é",
    "u00ea": "ê",
    "u00eb": "ë",
    "u00ec": "ì",
    "u00ed": "í",
    "u00ee": "î",
    "u00ef": "ï",
    "u00f0": "ð",
    "u00f1": "ñ",
    "u00f2": "ò",
    "u00f3": "ó",
    "u00f4": "ô",
    "u00f5": "õ",
    "u00f6": "ö",
    "u00f8": "ø",
    "u00f9": "ù",
    "u00fa": "ú",
    "u00fb": "û",
    "u00fc": "ü",
    "u00fd": "ý",
    "u00ff": "ÿ",
    "u0153": "œ",
    "&#x27;": "'",
}


def resolve_special_chars(location):
    matches = re.findall("(u00[\w+]{2}|&#x27;)", location)
    if matches != []:
        for special_char in matches:
            location = location.replace(special_char,
                                        special_chars.get(special_char, ""))
    return location


def launch_browser(option):
    if not option:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        return webdriver.Chrome("/usr/bin/chromedriver",
                                chrome_options=chrome_options)
    else:
        return webdriver.Chrome("/usr/bin/chromedriver")


def login(account, password):
    try:
        print(
            "Logging in with " + account + "'s Instagram account ...",
            end="\r",
        )
        browser.get("https://www.instagram.com/accounts/login/")
        time.sleep(1)  #find element won't work if this is removed

        login = browser.find_element_by_xpath("//input[@name='username']")
        passwd = browser.find_element_by_xpath("//input[@name='password']")
        login.send_keys(account)
        passwd.send_keys(password)
        login.submit()
        time.sleep(2)
        browser.get("https://www.instagram.com/" + args.target_account)
        return True
    except:
        return False


def scrolls(
    publications,
):  # scrolls required to snag all the data accordingly to the number of posts
    return (int(publications)) // 11
    # return 1 #for testing purpose


def fetch_urls(number_publications):
    links = []
    links.extend(re.findall("/p/([^/]+)/", browser.page_source))
    n_scrolls = scrolls(number_publications)

    for i in range(
            n_scrolls
    ):  # collecting all the pictures links in order to see which ones contains location data
        print(
            "Scrolling the Instagram target profile, fetching pictures URLs ..."
            + str(100 * i // n_scrolls) + "% of the profile scrolled ",
            end="\r",
        )
        browser.execute_script(
            "window.scrollTo(0, document.body.scrollHeight)")
        links.extend(re.findall("/p/([^/]+)/", browser.page_source))
        time.sleep(
            1
        )  # dont change this, otherwise some scrolls won't be effective and all the data won't be scrapped

    return list(dict.fromkeys(links))  # remove duplicates


def parse_location_timestamp(content):
    try:
        location = dict(
            resolve_special_chars(x).split(':')
            for x in re.search(r"location\":{(.*)(?=, \\\"exact_city_match)",
                               content).group(1).replace("\\", "").
            replace("\"", "").replace("address_json:{", "").split(",")
            if len(x.split(':')) > 1)

    except:
        location = "Error"
    if location != "Error":
        if logged_in:
            return [
                location,
                re.search('datetime="([^"]+)', content).group(1).split("T")[0]
            ]
        else:
            location.pop("has_public_page", None)
            return [
                location,
                re.search('"uploadDate":"([^"]+)"',
                          content).group(1).split("T")[0]
            ]
    else:
        return None


def fetch_locations_and_timestamps_not_logged(links):
    links_locations_timestamps = []
    count = 0
    sys.stdout.write("\033[K")
    max_wrk = 50
    print(
        "Fetching Locations and Timestamps on each picture ... " +
        str(len(links)) + " links processed asynchronously by a pool of " +
        str(max_wrk),
        end="\r",
    )
    executor = ThreadPoolExecutor(
        max_workers=max_wrk
    )  # didnt find any information about Instagram / Facebook Usage Policy ... people on stackoverflow say there's no limit if you're not using any API so ... ¯\_(ツ)_/¯
    loop = asyncio.get_event_loop()

    async def make_requests():
        futures = [
            loop.run_in_executor(executor, requests.get,
                                 "https://www.instagram.com/p/" + url)
            for url in links
        ]
        await asyncio.wait(futures)
        return futures

    futures = loop.run_until_complete(make_requests())
    number_locs = len(futures)

    for i in range(0, number_locs):
        content = futures[i].result().text
        location_timestamp = parse_location_timestamp(content)
        if location_timestamp != None:
            count += 1
            links_locations_timestamps.append([
                "https://www.instagram.com/p/" + links[i],
                location_timestamp[0],
                location_timestamp[1],
            ])

        print(
            "Parsing location data ... " + str(i) + "/" + str(number_locs) +
            " links processed... " + " Found location data on " + str(count) +
            " links",
            end="\r",
        )
    return links_locations_timestamps


def fetch_locations_and_timestamps_logged(links):
    links_locations_timestamps = []
    count = 1
    sys.stdout.write("\033[K")
    for link in links:  # iterate over the links, collect location and timestamps if a location is available on the Instagram post
        print("Checking Locations on each picture : Picture " + str(count) +
              " out of " + str(len(links)) + " - " +
              str(len(links_locations_timestamps)) + " Locations collected",
              end="\r")
        browser.get('https://www.instagram.com/p/' + link)
        location_timestamp = parse_location_timestamp(browser.page_source)
        if location_timestamp != None:
            count += 1
            links_locations_timestamps.append([
                "https://www.instagram.com/p/" + link,
                location_timestamp[0],
                location_timestamp[1],
            ])
    return links_locations_timestamps


def geocode(location_dict):
    query = "https://nominatim.openstreetmap.org/search"

    if location_dict.get(' city_name') != " ":
        query += "?city=" + location_dict.get(' city_name')[1:] + "&"
    else:
        query += "?q=" + location_dict.get("name").replace(
            "-", " ") + "&"  # second try?
        if location_dict.get('street_address') != " ":
            query += "?street=" + location_dict.get('street_address') + "&"
    if location_dict.get(' country_code') != " ":  #ISO 3166-1alpha2 code
        query += "countrycodes=" + location_dict.get(' country_code')[1:] + "&"
    # if location_dict.get(" zip_code") != "":
    #     query += "postalcode=" + str(location_dict(" zip_code")) + "&"
    return requests.get(query + "&format=json&limit=1").json()


def geocode_all(links_locations_and_timestamps):
    sys.stdout.write("\033[K")
    errors = 0
    cnt = 1
    gps_coordinates = []

    for location in links_locations_and_timestamps:
        print(
            "Fetching GPS Coordinates ... : Processing location number " +
            str(cnt) + " out of " + str(len(links_locations_and_timestamps)) +
            " - Number of errors:" + str(errors),
            end="\r",
        )
        try:
            tmp_geoloc = geocode(location[1])
            gps_coordinates.append(
                [tmp_geoloc[0]["lat"], tmp_geoloc[0]["lon"]])
        except:
            print("An exception occurred for: " + str(location[1]))
            errors += 1
            gps_coordinates.append("Error")
        time.sleep(
            1
        )  # Respect Nominatim's Usage Policy! (1 request per sec max) https://operations.osmfoundation.org/policies/nominatim/
        cnt += 1

    sys.stdout.write("\033[K")

    return gps_coordinates


def export_data(links_locations_and_timestamps, gps_coordinates):

    json_dump = []
    errors = []

    os.makedirs("output/" + args.target_account, exist_ok=True)

    for i in range(0, len(links_locations_and_timestamps)):
        links_locations_and_timestamps[i].append(gps_coordinates[i])
        if gps_coordinates[i] != "Error":
            json_dump.append({
                "link": links_locations_and_timestamps[i][0],
                "place": links_locations_and_timestamps[i][1],
                "timestamp": links_locations_and_timestamps[i][2],
                "gps": {
                    "lat": links_locations_and_timestamps[i][3][0],
                    "lon": links_locations_and_timestamps[i][3][1],
                },
            })
        else:
            errors.append(({
                "link": links_locations_and_timestamps[i][0],
                "place": links_locations_and_timestamps[i][1],
                "timestamp": links_locations_and_timestamps[i][2],
                "gps": "Error",
            }))
    with open(
            "output/" + args.target_account + "/" + args.target_account +
            "_instaloctrack_data.json", "w") as filehandle:
        json.dump(json_dump, filehandle)

    with open(
            "output/" + args.target_account + "/" + args.target_account +
            "_instaloctrack_errors.json", "w") as filehandle:
        json.dump(errors, filehandle)
    print(
        "Location names, timestamps, and GPS Coordinates were written to : output/"
        + args.target_account + "/" + args.target_account +
        "_instaloctrack_data.json")

    return len(json_dump), len(errors)


def map_locations():
    templateLoader = jinja2.FileSystemLoader(searchpath="./")
    templateEnv = jinja2.Environment(loader=templateLoader)
    template = templateEnv.get_template("template.html")
    outputText = template.render(
        target_account=args.target_account,
        publications_number=number_publications,
        retrieved_number=len(links_locations_and_timestamps),
        mapped_number=numbers[0],
        links=str([x[0] for x in links_locations_and_timestamps]),
        errors_number=len(links_locations_and_timestamps) - numbers[0],
        places=str([x[1] for x in links_locations_and_timestamps]),
        timestamps=str([x[2] for x in links_locations_and_timestamps]),
        locations=str(gps_coordinates),
    )

    with open(
            "output/" + args.target_account + "/" + args.target_account +
            "_instaloctrack_map.html", "w") as f:
        f.write(outputText)
        f.close()
        print("Map with all the markers was written to: output/" +
              args.target_account + "/" + args.target_account +
              "_instaloctrack_map.html")


browser = launch_browser(args.visual)

logged_in = False

if args.login is not None and args.password is not None:
    logged_in = login(args.login, args.password)

browser.get("https://www.instagram.com/" + args.target_account + "/?hl=fr")

number_publications = re.search("([0-9]+)</span> publications",
                                browser.page_source).group(1)

links = fetch_urls(number_publications)
if logged_in:
    links_locations_and_timestamps = fetch_locations_and_timestamps_logged(
        links)
else:
    browser.quit()
    links_locations_and_timestamps = fetch_locations_and_timestamps_not_logged(
        links)

gps_coordinates = geocode_all(links_locations_and_timestamps)

numbers = export_data(links_locations_and_timestamps, gps_coordinates)
map_locations()
