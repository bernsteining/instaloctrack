import argparse
import asyncio
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Optional, Any

import coloredlogs
import enlighten
import jinja2
import pycountry
import pycountry_convert
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def parse_args():
    """Parse console arguments."""
    parser = argparse.ArgumentParser(
        description=
        "Instagram location data gathering tool.  Usage: python3instaloctrack.py -t <target_account>",
        prog="instaloctrack")

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
        "-o",
        "--output_directory",
        dest="output_directory",
        help=
        "Directory where results are saved. If the directory doesn't exist, it's created.",
    )

    parser.add_argument(
        "-v",
        "--visual",
        action='store_true',
        help="Spawns Chromium GUI, otherwise Chromium is headless",
    )

    return parser.parse_args()


def print_banner():
    banner = """
                                        -------------------------------------------------------
   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄  | instaloctrack 1.1                                   |
   █░░░░░░░░▀█▄▀▄▀██████░▀█▄▀▄▀██████░  |                                                     |
   ░░░░░░░░░░░▀█▄█▄███▀░░░░▀█▄█▄███░░░  | A Python3 tool to scrape location data on Instagram.|
                                        |                                                     |
                                        | www.github.com/bernsteining/instaloctrack           |                                                                                                |                                                     |
                                        -------------------------------------------------------
	 """
    print(banner)


def init_logger():
    """Initialize the logger of the program. """
    logger: logging.Logger = logging.getLogger(__name__)
    coloredlogs.install(level='INFO',
                        logger=logger,
                        fmt='[+] %(asctime)s - %(message)s',
                        stream=sys.stdout)

    return logger


def selenium_to_requests_session(browser: webdriver.chrome):
    """Transfer selenium's session cookies to requests session."""
    selenium_cookies: List[Dict[str, str]] = browser.get_cookies()

    requests_session: requests.sessions.Session = requests.Session()

    for cookie in selenium_cookies:
        requests_session.cookies.set(cookie.get("name"), cookie.get("value"))

    return requests_session


def resolve_special_chars(location: str):
    """Handle special characters that aren't correctly encoded."""
    matches: List[str] = re.findall("(u0[\w+]{3}|&#x27;)", location)
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


def launch_browser(option: bool):
    """Launch the ChromeDriver with specific options."""
    if not option:
        chrome_options = Options()
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument("--headless")
        return webdriver.Chrome("/usr/bin/chromedriver",
                                chrome_options=chrome_options)
    else:
        return webdriver.Chrome("/usr/bin/chromedriver")


def login(args: argparse.Namespace, browser: webdriver.chrome, account: str,
          password: str, logger: logging.Logger):
    """Login to the Instagram account."""
    logger.info(f"Logging in with {account}'s Instagram account ...")

    browser.get("https://www.instagram.com/accounts/login/")
    time.sleep(1)  #find element won't work if this is removed

    login = browser.find_element_by_xpath("//input[@name='username']")
    passwd = browser.find_element_by_xpath("//input[@name='password']")
    login.send_keys(account)
    passwd.send_keys(password)
    login.submit()
    time.sleep(2)

    browser.get(f"https://www.instagram.com/{account}/saved/?hl=fr")

    if not "Page introuvable" in browser.page_source:
        return True
    else:
        logger.setLevel(logging.ERROR)
        logger.error("Could not log into " + account +
                     "'s Instagram account. ")
        return False


def scrolls(publications: int):
    """Number of scrolls required to catch all the pictures links."""
    return (publications) // 11


def fetch_urls(browser, number_publications, logger):
    """Catch all the pictures links of the Instagram profile."""
    links = []
    links.extend(re.findall("/p/([^/]+)/", browser.page_source))
    n_scrolls = scrolls(number_publications)

    logger.info(
        "Scrolling the Instagram target profile, scraping pictures URLs ... ")

    pbar = enlighten.Counter(total=n_scrolls, desc='Scrolling', unit='scrolls')

    for _ in range(
            n_scrolls
    ):  # collecting all the pictures links in order to see which ones contains location data
        pbar.update()
        browser.execute_script(
            "window.scrollTo(0, document.body.scrollHeight)")
        links.extend(re.findall("/p/([^/]+)/", browser.page_source))
        time.sleep(
            1
        )  # dont change this, otherwise some scrolls won't be effective and all the data won't be scrapped
    logger.info("Pictures links collected successfully")
    return list(dict.fromkeys(links))  # remove duplicates


def parse_location_timestamp(content: str):
    """Catch the location data and the timestamps in the page source."""
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


def fetch_locations_and_timestamps(
    links: List[str],
    logger: logging.Logger,
    requests_session: Optional[requests.sessions.Session] = None):
    """Catch all locations and timestamps asynchronously on a profile."""
    links_locations_timestamps = []
    count: int = 0
    max_wrk: int = len(links)

    logger.info("Scraping Locations and Timestamps on each picture: " +
                str(len(links)) + " links processed asynchronously")

    executor = ThreadPoolExecutor(
        max_workers=max_wrk
    )  # didnt find any information about Instagram / Facebook Usage Policy ... people on stackoverflow say there's no limit if you're not using any API so ... ¯\_(ツ)_/¯
    loop = asyncio.get_event_loop()

    async def make_requests(
        requests_session: Optional[requests.sessions.Session]):
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
    number_locs: int = len(futures)

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
    logger.info(
        f"Location data scrapped successfully, found {count} locations.")
    return links_locations_timestamps


def geocode_by_name(name: str):
    """Get the GPS coordinates of a location by its name field."""
    return requests.get(
        f"https://nominatim.openstreetmap.org/search?q={name}&format=json&limit=1"
    ).json()


def geocode(location_dict: Dict[Any, Any]):
    """Get the GPS coordinates of a location."""
    query: str = "https://nominatim.openstreetmap.org/search?"

    street: str = location_dict.get('street_address')[1:]

    if location_dict.get(' country_code') != " ":  #ISO 3166-1alpha2 code
        query += "countrycodes=" + location_dict.get(' country_code')[1:] + "&"
    if street and len(street.split()) >= 3:
        query += "street=" + street + "&"
    if location_dict.get(' city_name') != " ":
        query += "city=" + location_dict.get(' city_name')[1:] + "&"

    else:
        query += "q=" + location_dict.get("name").replace("-", " ") + "&"

    return requests.get(query + "format=json&limit=1").json()


def geocode_all(links_locations_and_timestamps: List[Any],
                logger: logging.Logger):
    """Get the GPS coordinates of all the locations."""
    errors: int = 0
    track_errors = []
    cnt: int = 0
    gps_coordinates = []
    location_number: int = len(links_locations_and_timestamps)

    # Geocoding progress bar
    pbar = enlighten.Counter(total=location_number,
                             desc='Geocoding',
                             unit='location',
                             position=30)

    pbar_errors = pbar.add_subcounter('yellow')
    logger.info("Geocoding Locations ...")

    for location in links_locations_and_timestamps:
        try:
            tmp_geoloc = geocode(location[1])
            gps_coordinates.append(
                [tmp_geoloc[0]["lat"], tmp_geoloc[0]["lon"]])
            pbar.update()
        except:
            logger.warning("An exception occurred for: " + str(location[1]))
            errors += 1
            track_errors.append(cnt)
            gps_coordinates.append("Error")
            pbar_errors.update()
        time.sleep(
            1
        )  # Respect Nominatim's Usage Policy! (1 request per sec max) https://operations.osmfoundation.org/policies/nominatim/
        cnt += 1

    # Error correction progress bar
    pbar_solve = enlighten.Counter(total=errors,
                                   desc='Correcting Errors',
                                   unit='location',
                                   position=30)

    logger.info("Correcting geocoding errors with another query ...")
    errors_solved: int = 0
    for index in track_errors:
        try:
            tmp_geoloc = geocode_by_name(
                links_locations_and_timestamps[index][1].get("name"))
            gps_coordinates[index] = [
                tmp_geoloc[0]["lat"], tmp_geoloc[0]["lon"]
            ]
            errors_solved += 1
        except:
            logger.warning("Still could not geocode: " +
                           str(links_locations_and_timestamps[index][1]))
        time.sleep(
            1
        )  # Respect Nominatim's Usage Policy! (1 request per sec max) https://operations.osmfoundation.org/policies/nominatim/
        pbar_solve.update()

    errors = errors - errors_solved

    if errors == 0:
        logger.info("Geocoding: OK, 100% Correct")
    else:
        percent_errors = (errors / location_number) * 100

        logger.warning("Geocoding: DONE with " + str(percent_errors) + "%" +
                       " of errors: " + str(errors) + " out of " +
                       str(location_number))
    return gps_coordinates


def stats(links_locations_and_timestamps: List[Any]):
    """Compute some statistics about the user's location."""
    countrycodes_dict = dict()
    continents_dict = dict()

    countrycodes = [
        x[1].get(" country_code")[1:] for x in links_locations_and_timestamps
    ]

    continents = {
        'NA': 'North America',
        'SA': 'South America',
        'AS': 'Asia',
        'OC': 'Australia',
        'AF': 'Africa',
        'EU': 'Europe',
    }

    for countrycode in countrycodes:
        try:
            country = pycountry.countries.get(alpha_2=countrycode).name

            if country in countrycodes_dict:
                countrycodes_dict[country] += 1
            else:
                countrycodes_dict.update({country: 1})
        except:
            pass

        try:
            continent = continents.get(
                pycountry_convert.country_alpha2_to_continent_code(
                    countrycode))
            if continent in continents_dict:
                continents_dict[continent] += 1
            else:
                continents_dict.update({continent: 1})
        except:
            pass
    return (countrycodes_dict, continents_dict)


def create_output_directory(output_path: Path, logger: logging.Logger) -> None:
    """Create the output directory if it doesn't exist.

    Parameters
    ----------
    output_path : Path
        Path of the directory where to save the JSON.
    logger : logging.Logger
        Logger of the program.

    Raises
    ------
    NotADirectoryError
        If the provided output_path is not a directory.

    """
    if Path(output_path).exists() and not Path(output_path).is_dir():
        raise NotADirectoryError("The -o parameter should be a directory.")

    if not Path(output_path).exists():
        Path(output_path).mkdir(parents=True, exist_ok=True)
        if Path(output_path).exists():
            logger.info(
                f"Output directory successfully created at: {output_path}")
        else:
            logger.error(f"Unable to create output directory.")
            raise OSError("Unable to create output directory.")


def export_data(args: argparse.Namespace,
                links_locations_and_timestamps: List[Any],
                gps_coordinates: List[Any], logger: logging.Logger):
    """Write to JSON all the data retrieved."""

    json_dump: List[Any] = []
    errors: List[Any] = []

    if args.output_directory:
        base_path: Path = Path(
            f"{args.output_directory}/{args.target_account}/")
        create_output_directory(base_path, logger)
    else:
        base_path: Path = Path(f"output/{args.target_account}/")
        create_output_directory(base_path, logger)

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
    with open(base_path.joinpath(f"{args.target_account}_instaloctrack_data.json"),
              "w") as filehandle:
        json.dump(json_dump, filehandle)

    with open(base_path.joinpath(f"{args.target_account}_instaloctrack_errors.json"),
              "w") as filehandle:
        json.dump(errors, filehandle)
    logger.info(
        f"Picture links, Location names, timestamps, and GPS Coordinates were written to : {base_path}"
        + args.target_account + "_instaloctrack_data.json")

    return len(json_dump), len(errors)


def map_locations(args: argparse.Namespace, number_publications: int, numbers,
                  links_locations_and_timestamps, gps_coordinates,
                  countrycodes_for_js, continents_for_js,
                  logger: logging.Logger):
    """Pin all the locations on on an interactive map."""
    templateLoader = jinja2.FileSystemLoader(searchpath=str(Path(__file__).parent))
    templateEnv = jinja2.Environment(loader=templateLoader)
    template = templateEnv.get_template("templates/template.html")
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

    if args.output_directory:
        base_path: Path = Path(
            f"{args.output_directory}/{args.target_account}/")
    else:
        base_path: Path = Path(f"output/{args.target_account}/")

    with open(base_path.joinpath(f"{args.target_account}_instaloctrack_map.html"),
              "w") as f:
        f.write(outputText)
        logger.info(
            "Interactive pinned map, Heatmap, and Statistics are available in: output/"
            + args.target_account + "/" + args.target_account +
            "_instaloctrack_map.html")


def main():

    print_banner()
    args: argparse.Namespace = parse_args()
    browser: webdriver.chrome = launch_browser(args.visual)

    logger: logging.Logger = init_logger()

    logged_in: bool = False

    if args.login is not None and args.password is not None:
        logged_in = login(args, browser, args.login, args.password, logger)
        if not logged_in:
            exit()

    browser.get("https://www.instagram.com/" + args.target_account + "/?hl=fr")

    number_publications: int = int(
        re.search("([0-9]+)</span> publications",
                  browser.page_source).group(1))

    links: List[str] = fetch_urls(browser, number_publications, logger)

    requests_session: Optional[webdriver.chrome] = None
    if logged_in:
        requests_session = selenium_to_requests_session(browser)
    browser.quit()
    links_locations_and_timestamps = fetch_locations_and_timestamps(
        links, logger, requests_session)

    gps_coordinates = geocode_all(links_locations_and_timestamps, logger)

    numbers = export_data(args, links_locations_and_timestamps,
                          gps_coordinates, logger)

    (countrycodes, continents) = stats(links_locations_and_timestamps)
    countrycodes_for_js = [[k, v] for k, v in countrycodes.items()]
    continents_for_js = [[k, v] for k, v in continents.items()]
    map_locations(args, number_publications, numbers,
                  links_locations_and_timestamps, gps_coordinates,
                  countrycodes_for_js, continents_for_js, logger)


if __name__ == "__main__":
    main()
