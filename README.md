# Insta LocTrack

A SOCMINT project I made in this week for an OSINT course I had.

TL;DR : Here's a video of the script being launched : [https://www.youtube.com/watch?v=BKlTnBWupr0](https://www.youtube.com/watch?v=BKlTnBWupr0)

## Goal of the project
The goal of this project is to collect all the locations linked to the photos of an Instagram profile in order to place them on a map.

I doesn't use Instagram's API since Instagram deprecated its location functionality in 2018, and also because I wanted to play with Selenium and Chromedriver to make my own scraper.

## requirements

sudo apt install chromium-chromedriver &&
pip install selenium requests

## How it works

First, we retrieve all the pictures links of the account by scrolling the whole Instagram profile, thanks to selenium's webdriver.

Then, for each picture link, we check if it contains a location in the picture description, and retrieve the location's data if there's one, and the timestamp.

* **NB:** Since 2018 Instagram deprecated its location API and it's not possible anymore to get the GPS coordinates of a picture, all we can retrieve is the name of the location. (If you can prove me that I'm wrong about this, please tell me!)

Because Instagram doesn't provide GPS coordinates, and we're only given names of places, we have to geocode these (.ie. get the GPS coords from the name's place).

For this, I used Nominatim's awesome API, which uses OpenStreetMap. For our usage, no API key is required, and we respect [Nominatim's usage Policy](https://operations.osmfoundation.org/policies/nominatim/) by requesting GPS coordinatess once every second.

Eventually, once we have all the GPS coordinatess, we generate a HTML page with Javascript embedded that plots a Google Map with all our locations pinned. Once again, no API key is required for this step.
For this final step, I have to thank [Tania Rascia's project](https://www.taniarascia.com/google-maps-apis-for-multiple-locations/) which provides such a feature.

Also, the data collected by the script (location names, timestamps, GPS coordinates) are dumped to a JSON file in order to be re-used.



## Example

As an example, here's the output on the former French President's Instagram profile, [@fhollande](https://www.instagram.com/fhollande/?hl=fr) :

As you can see, some locations aren't accurate enough to geocode them. The script handles this errors, and alerts the user about them on the console.

The map:
![Map of @fhollande's locations on Instagram](https://imgur.com/FRaa2zO.png
)

Information available when clicking on a marker:

![JSON data on map marker](https://imgur.com/dJfrq0O.png)

The JSON data dump (just a part of it to show the format for a given location):

     {
    "link": "https://www.instagram.com/p/9L4rP-x9aO",
    "place": "athens greece",
    "timestamp": "2015-10-23",
    "gps": {
      "lat": "37.9841493",
      "lon": "23.7279843"
    }




## Possible Improvements

* Cleaner code :D
* Time information about the duration of the script
* Templating using web2py, django or jinja2 to generate the web map instead of hardcoding the HTML in the script. Might be an overkill tho
* Use requests instead of chromedriver to fetch the locations and parallelize this part
*  On Instagram's mobile App, it's possible to get the exact coordinates within a few clicks on the location's information ... maybe we could use this technique while scraping to get the exact GPS coords? 
* Keep a track of the errors encountered during the script : Sometimes some location names aren't precise enough for Nominatim to geocode it ... We might want to keep these informations in a JSON rather than just print on the console.
* Add an argument to select only a set of pictures (selected by date, or rank)
* Find the best way to geocode : Since the location is the user/community manager input, it can have mistakes / be very inaccurate... Maybe we could try to check if a country name is in the location name in order to minimize mistakes, and then use Normatim's specific field!
