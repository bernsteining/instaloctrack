import argparse
import asyncio
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import jinja2
import pycountry_convert as pc
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def parse_args():
    """Parse console arguments"""
    parser = argparse.ArgumentParser(
        description=
        "Instagram location data gathering tool.  Usage: python3 InstaLocTrack.py -t <target_account>",
        prog="InstaLocTrack")

    parser.add_argument(
        "-t",
        "--target",
        dest="target_account",
        help="Instagram profile to investigate",
        required=True,
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

    return parser.parse_args()


def selenium_to_requests_session(browser):
    selenium_cookies = browser.get_cookies()

    requests_session = requests.Session()

    for cookie in selenium_cookies:
        requests_session.cookies.set(cookie.get("name"), cookie.get("value"))

    return requests_session


def resolve_special_chars(location):
    """Handle special characters that aren't correctly encoded"""
    matches = re.findall("(u0[\w+]{3}|&#x27;)", location)
    if matches != []:
        for special_char in matches:
            if special_char != "&#x27;":
                tmp_char = "\\" + special_char
                location = location.replace(
                    special_char,
                    tmp_char.encode().decode('unicode-escape'))
            else:
                location = location.replace(special_char, "'")
    return location


def launch_browser(option):
    """Launch the ChromeDriver with specific options"""
    if not option:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        return webdriver.Chrome("/usr/bin/chromedriver",
                                chrome_options=chrome_options)
    else:
        return webdriver.Chrome("/usr/bin/chromedriver")


def login(args, browser, account, password):
    """Login to the Instagram account"""
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


def scrolls(publications, ):
    """Number of scrolls required to catch all the pictures links"""
    return (int(publications)) // 11


def fetch_urls(browser, number_publications):
    """Catch all the pictures links of the Instagram profile"""
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
    """Catch the location data and the timestamps in the page source"""
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
        location.pop("has_public_page", None)
        try:
            datetime = re.search('"uploadDate":"([^"]+)"',
                                 content).group(1).split("T")[0]
        except:
            datetime = "unknown"
        return [location, datetime]
    else:
        return None


def fetch_locations_and_timestamps(links, requests_session=None):
    """Catch all locations and timestamps asynchronously on a profile"""
    links_locations_timestamps = []
    count = 0
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

    async def make_requests(requests_session):
        if requests_session:
            session = requests_session
        else:
            session = requests.Session()
        futures = [
            loop.run_in_executor(executor, session.get,
                                 "https://www.instagram.com/p/" + url)
            for url in links
        ]
        await asyncio.wait(futures)
        return futures

    futures = loop.run_until_complete(make_requests(requests_session))
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


def geocode(location_dict):
    """Get the GPS coordinates of a location"""
    query = "https://nominatim.openstreetmap.org/search"

    if location_dict.get(' country_code') != " ":  #ISO 3166-1alpha2 code
        query += "countrycodes=" + location_dict.get(' country_code')[1:] + "&"
    if location_dict.get(' city_name') != " ":
        query += "?city=" + location_dict.get(' city_name')[1:] + "&"
        # if location_dict.get(" zip_code") != "":
        #     query += "postalcode=" + location_dict(" zip_code")[1:] + "&"

    else:
        query += "?q=" + location_dict.get("name").replace(
            "-", " ") + "&"  # second try?
        if location_dict.get('street_address') != " ":
            query += "?street=" + location_dict.get('street_address') + "&"

    return requests.get(query + "&format=json&limit=1").json()


def geocode_all(links_locations_and_timestamps):
    """Get the GPS coordinates of all the locations"""
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

    return gps_coordinates


def stats(links_locations_and_timestamps):
    countrycodes_dict = dict()
    continents_dict = dict()

    countrycodes = [
        x[1].get(" country_code")[1:] for x in links_locations_and_timestamps
    ]

    for countrycode in countrycodes:
        if countrycode in countrycodes_dict:
            countrycodes_dict[countrycode] += 1
        else:
            countrycodes_dict.update({countrycode: 1})

        try:
            continent = pc.country_alpha2_to_continent_code(countrycode)
        except:
            pass
        if continent in continents_dict:
            continents_dict[continent] += 1
        else:
            continents_dict.update({continent: 1})

    return (countrycodes_dict, continents_dict)


def export_data(args, links_locations_and_timestamps, gps_coordinates):
    """Write to JSON all the data"""

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


def map_locations(args, number_publications, numbers,
                  links_locations_and_timestamps, gps_coordinates,
                  countrycodes_for_js, continents_for_js):
    """Pin all the locations on on an interactive map"""
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
        countrycodes=str(countrycodes_for_js),
        continents=str(continents_for_js))

    with open(
            "output/" + args.target_account + "/" + args.target_account +
            "_instaloctrack_map.html", "w") as f:
        f.write(outputText)
        f.close()
        print("Map with all the markers was written to: output/" +
              args.target_account + "/" + args.target_account +
              "_instaloctrack_map.html")


def main():

    args = parse_args()
    browser = launch_browser(args.visual)

    logged_in = False

    if args.login is not None and args.password is not None:
        logged_in = login(args, browser, args.login, args.password)

    browser.get("https://www.instagram.com/" + args.target_account + "/?hl=fr")

    number_publications = re.search("([0-9]+)</span> publications",
                                    browser.page_source).group(1)

    links = fetch_urls(browser, number_publications)
    requests_session = None
    if logged_in:
        requests_session = selenium_to_requests_session(browser)
    browser.quit()
    links_locations_and_timestamps = fetch_locations_and_timestamps(
        links, requests_session)

    gps_coordinates = geocode_all(links_locations_and_timestamps)

    numbers = export_data(args, links_locations_and_timestamps,
                          gps_coordinates)

    (countrycodes, continents) = stats(links_locations_and_timestamps)
    countrycodes_for_js = [[k, v] for k, v in countrycodes.items()]
    continents_for_js = [[k, v] for k, v in continents.items()]
    map_locations(args, number_publications, numbers,
                  links_locations_and_timestamps, gps_coordinates,
                  countrycodes_for_js, continents_for_js)


if __name__ == "__main__":
    main()
