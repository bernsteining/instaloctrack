# instaloctrack


TL;DR : [ascineema](https://asciinema.org/a/IeWgAH6UuxPokyGxp8uUl1Xw3), [video of the project](https://www.youtube.com/watch?v=XVouSOwRDGE)

A tool to scrape geotagged locations on Instagram profiles. Output in JSON & interactive map.


## requirements

```
sudo apt install chromium-chromedriver && chmod a+x /usr/bin/chromedriver
```
## 🛠️ installation

```
git clone https://github.com/bernsteining/instaloctrack
cd instaloctrack
pip3 install .
```

Or use Docker:

```
sudo docker build -t instaloctrack -f Dockerfile .
```

## Usage

    instaloctrack -h
    usage: instaloctrack [-h] [-t TARGET_ACCOUNT] [-l LOGIN] [-p PASSWORD] [-v]

    Instagram location data gathering tool. Usage: python3 instaloctrack.py -t <target_account>

    optional arguments:
      -h, --help            show this help message and exit
      -t TARGET_ACCOUNT, --target TARGET_ACCOUNT
                            Instagram profile to investigate
      -l LOGIN, --login LOGIN
                            Instagram profile to connect to, in order to access
                            the instagram posts of the target account
      -p PASSWORD, --password PASSWORD
                            Password of the Instagram profile to connect to
      -v, --visual          Spawns Chromium GUI, otherwise Chromium is headless

e.g.

```
instaloctrack -t <target_account>
```

If the target profile is private and you have an account following the target profile you can scrape the data with a connected session:


```
instaloctrack -t <target_account> -l <your_account> -p <your_password>
```

or with Docker:

```
sudo docker run -v /tmp/output:/tmp/output instaloctrack -t <target_account> -o /tmp/output
```

## ⚙️ How it works

First, we retrieve all the pictures links of the account by scrolling the whole Instagram profile, thanks to selenium's webdriver.

Then, we retrieve asynchronously (asyncio) each picture link, we check if it contains a location in the picture description, and retrieve the location's data if there's one, and the timestamp.

* **NB:** Since 2018 Instagram deprecated its location API and it's not possible anymore to get the GPS coordinates of a picture, all we can retrieve is the name of the location. (If you can prove me that I'm wrong about this, please tell me!)

Because Instagram doesn't provide GPS coordinates, and we're only given names of places, we have to geocode these (.ie. get the GPS coords from the name's place).

For this, I used Nominatim's awesome API, which uses OpenStreetMap. For our usage, no API key is required, and we respect [Nominatim's usage Policy](https://operations.osmfoundation.org/policies/nominatim/) by requesting GPS coordinatess once every second.

Eventually, once we have all the GPS coordinatess, we generate a HTML (thanks to jinja2 templating) with Javascript embedded that plots an Open Street Map (thanks to [Leaflet](https://github.com/Leaflet/Leaflet) library) with all our locations pinned. Once again, no API key is required for this step.

Also, the data collected by the script (location names, timestamps, GPS coordinates, errors) are dumped to a JSON file in order to be re-used.

## Example

As an example, here's the output on the former French President's Instagram profile, [@fhollande](https://www.instagram.com/fhollande/?hl=fr):

![Map of @fhollande's locations on Instagram](https://i.imgur.com/LPulybM.png)

The Heatmap:

![Heatmap of @fhollande's locations on Instagram](https://i.imgur.com/OBrTTdp.png)

Information available when clicking on a marker:

![available data when clicking on a marker](https://imgur.com/QBIofFs.png)

Stats about the location data:

![stats about the location data](https://imgur.com/rraBZ1n.png)

The JSON data dump (just a part of it to show the format for a given location):

    {
        "link": "https://www.instagram.com/p/-Q_9EvR9eu",
        "place": {
          "id": "290297",
          "name": "Musée du quai Branly - Jacques Chirac",
          "slug": "musee-du-quai-branly-jacques-chirac",
          "street_address": " 37 quai Branly",
          " zip_code": " 75007",
          " city_name": " Paris",
          " region_name": " ",
          " country_code": " FR"
        },
        "timestamp": "2015-11-19",
        "gps": {
          "lat": "48.8566969",
          "lon": "2.3514616"
        }
      }




## Possible Improvements

* Cleaner code :D
* Factorize the geocoding function which is waaay too long and cryptic
* Use beautifulsoup instead of regex parsing
* Remove weird blank space caused by progress bar
* Use other geocoding tools (e.g. https://geo.api.gouv.fr/adresse) than Nominatim when it fails? (specify arg?)
	* Use [geopy](https://pypi.org/project/geopy/) ?
	* Use Overpass instead of Nominatim ?
* Add an argument to select only a set of pictures (selected by date, or rank)
* Time information about the duration of the script
