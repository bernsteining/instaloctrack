from selenium import webdriver
import time
import re
import json
import requests
import sys
import asyncio 
import jinja2
from concurrent.futures import ThreadPoolExecutor

if len(sys.argv) < 2:
  print("Usage: python3 instaloctrack.py <username>")
  exit()

username = sys.argv[1] #Instagram account to investigate
browser = webdriver.Chrome('/usr/bin/chromedriver')
browser.get('https://www.instagram.com/'+username+'/?hl=fr')

number_publications = browser.find_element_by_xpath("/html/body").text.strip().split("\n")[3].split(" ")[0] 

special_chars =  {
    "\\u00c0" : "À",
    "\\u00c1" : "Á",
    "\\u00c2" : "Â",
    "\\u00c3" : "Ã",
    "\\u00c4" : "Ä",
    "\\u00c5" : "Å",
    "\\u00c6" : "Æ",
    "\\u00c7" : "Ç",
    "\\u00c8" : "È",
    "\\u00c9" : "É",
    "\\u00ca" : "Ê",
    "\\u00cb" : "Ë",
    "\\u00cc" : "Ì",
    "\\u00cd" : "Í",
    "\\u00ce" : "Î",
    "\\u00cf" : "Ï",
    "\\u00d1" : "Ñ",
    "\\u00d2" : "Ò",
    "\\u00d3" : "Ó",
    "\\u00d4" : "Ô",
    "\\u00d5" : "Õ",
    "\\u00d6" : "Ö",
    "\\u00d8" : "Ø",
    "\\u00d9" : "Ù",
    "\\u00da" : "Ú",
    "\\u00db" : "Û",
    "\\u00dc" : "Ü",
    "\\u00dd" : "Ý",
    "\\u00df" : "ß",
    "\\u00e0" : "à",
    "\\u00e1" : "á",
    "\\u00e2" : "â",
    "\\u00e3" : "ã",
    "\\u00e4" : "ä",
    "\\u00e5" : "å",
    "\\u00e6" : "æ",
    "\\u00e7" : "ç",
    "\\u00e8" : "è",
    "\\u00e9" : "é",
    "\\u00ea" : "ê",
    "\\u00eb" : "ë",
    "\\u00ec" : "ì",
    "\\u00ed" : "í",
    "\\u00ee" : "î",
    "\\u00ef" : "ï",
    "\\u00f0" : "ð",
    "\\u00f1" : "ñ",
    "\\u00f2" : "ò",
    "\\u00f3" : "ó",
    "\\u00f4" : "ô",
    "\\u00f5" : "õ",
    "\\u00f6" : "ö",
    "\\u00f8" : "ø",
    "\\u00f9" : "ù",
    "\\u00fa" : "ú",
    "\\u00fb" : "û",
    "\\u00fc" : "ü",
    "\\u00fd" : "ý",
    "\\u00ff" : "ÿ",
    "&#x27;" : "'"
}

def resolve_special_chars(location):
    matches = re.findall("(\\\\u00[\w+]{2}|&#x27;)", location) #catch special chars
    if matches != []:
      for special_char in matches:
            location = location.replace(special_char,special_chars.get( special_char, ""))
    return location
        
def scrolls(publications): # scrolls required to snag all the data accordingly to the number of posts
    return (int(publications))//11
    #return 1 #for testing purpose

def fetch_urls(number_publications):
  links = []
  links.extend(re.findall('/p/([^/]+)/', browser.page_source)) 
  n_scrolls = scrolls(number_publications)

  for i in range(n_scrolls): # collecting all the pictures links in order to see which ones contains location data
    print("Scrolling the Instagram profile, fetching pictures URLs ..." + str(100*i//n_scrolls) + "% of the profile scrolled ", end="\r")
    browser.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    links.extend(re.findall('/p/([^/]+)/', browser.page_source)) 
    time.sleep(1) # dont change this, otherwise some scrolls won't be effective and all the data won't be scrapped

  return list(dict.fromkeys(links)) # remove duplicates

def parse_location_timestamp(content):
    location = []
    try:
        address = re.search(r'\\/explore\\/locations\\/[0-9]+\\/([^/]+)\\/', content).group(1).replace("-", " ")
        address = resolve_special_chars(address)
    except:
        address= "Error"
    
    try:
        city = re.search('"addressLocality":"([^"]+)"', content)[0].split(":")[1].split(",")[0].replace("\"", "")
        #city = re.search('"city_name":"([^"]+)"', content)[0].split(":")[1].split(",")[0].replace("\"", "")
        city = resolve_special_chars(city)
              
    except:
        city = "Error"
    
    try:
        countrycode = re.search('Country","name":"([^"]+)"', content)[0].split(":")[1].replace("\"", "")
        countrycode = resolve_special_chars(countrycode)
    except:
        countrycode = "Error"
    
    location.extend([address, city, countrycode])

    if location != ["Error", "Error", "Error"]:
        tmp_timestamp = re.search('"uploadDate":"([^"]+)"', content)[0].split('T')[0]
        return [location,re.sub('[^0-9\-]', '', tmp_timestamp)]
    else:
        return None

def fetch_locations_and_timestamps(links):
  sys.stdout.write("\033[K")
  max_wrk = 50
  print("Fetching Locations and Timestamps on each picture ... " + str(len(links)) + " links processed asynchronously by a pool of " + str(max_wrk) , end="\r")
  executor = ThreadPoolExecutor(max_workers=max_wrk) # didnt find any information about Instagram / Facebook Usage Policy ... people on stackoverflow say there's no limit if you're not using any API so ... ¯\_(ツ)_/¯
  loop = asyncio.get_event_loop()

  async def make_requests():
    futures = [loop.run_in_executor(executor, requests.get, 'https://www.instagram.com/p/' + url) for url in links]
    await asyncio.wait(futures)
    return futures

  links_locations_timestamps = []
  futures = loop.run_until_complete(make_requests())
  number_locs = len(futures)
  count = 0

  for i in range(0, number_locs):
    content = futures[i].result().text
    location_timestamp = parse_location_timestamp(content)
    if location_timestamp != None:
      count += 1
      links_locations_timestamps.append(['https://www.instagram.com/p/'+links[i], location_timestamp[0], location_timestamp[1]])
      
    print("Parsing location data ... " + str(i) + "/" + str(number_locs) + " links processed... " + " Found location data on " + str(count) + " links" , end="\r")
  tmplist = [x[0] for x in links_locations_timestamps]
  print(tmplist)
  return links_locations_timestamps



def geocode(location):
    query = "https://nominatim.openstreetmap.org/search?"
    if location[0] != "Error":
        query += "q=" + resolve_special_chars(location[0]) + "&"
    if location[1] != "Error":
        query += "city=" + location[1] + "&"
    if location[2] != "Error":
        query += "countrycodes=" + location[2] + "&"
    return requests.get(query + "&format=json&limit=1").json()[0]

def geocode_all(links_locations_and_timestamps):
  sys.stdout.write("\033[K")
  errors = 0
  count = 1
  gps_coordinates = []

  for location in links_locations_and_timestamps:
      print("Fetching GPS Coordinates ... : Processing location number " + str(count) + " out of " + str(len(links_locations_and_timestamps)) + " - Number of errors:" + str(errors), end="\r")
      try:
          tmp_geoloc = geocode(location[1])
          gps_coordinates.append([tmp_geoloc['lat'], tmp_geoloc['lon']])
      except:
          print("An exception occurred for: " + str(location[1]))
          errors+=1
          gps_coordinates.append("Error")
      time.sleep(1) # Respect Normatim's Usage Policy! (1 request per sec max) https://operations.osmfoundation.org/policies/nominatim/
      count+=1
      
  sys.stdout.write("\033[K")

  return gps_coordinates

def export_data(links_locations_and_timestamps, gps_coordinates):

  json_dump = []
  errors = []

  for i in range(0, len(links_locations_and_timestamps)):
    links_locations_and_timestamps[i].append(gps_coordinates[i])
    if gps_coordinates[i] != "Error":
      json_dump.append({"link" : links_locations_and_timestamps[i][0],"place" : links_locations_and_timestamps[i][1], "timestamp" : links_locations_and_timestamps[i][2], "gps" : {"lat" : links_locations_and_timestamps[i][3][0] ,  "lon" : links_locations_and_timestamps[i][3][1]}})
    else:
      errors.append(({"link" : links_locations_and_timestamps[i][0],"place" : links_locations_and_timestamps[i][1], "timestamp" : links_locations_and_timestamps[i][2], "gps" : "Error"}))
  with open(username + '_instaloctrack_data.json', 'w') as filehandle:
    json.dump(json_dump, filehandle)

  with open(username + '_instaloctrack_errors.json', 'w') as filehandle:
    json.dump(errors, filehandle)
  print("Location names, timestamps, and GPS Coordinates were writtent to : " + username + '_instaloctrack_data.json')

  return len(json_dump),len(errors)

def map_locations():
  templateLoader = jinja2.FileSystemLoader(searchpath="./")
  templateEnv = jinja2.Environment(loader=templateLoader)
  template = templateEnv.get_template("template.html")
  outputText = template.render(username=username, 
                                                              publications_number=number_publications, 
                                                              retrieved_number=len(links_locations_and_timestamps), 
                                                              mapped_number=numbers[0], 
                                                              links=str([x[0] for x in links_locations_and_timestamps]), 
                                                              errors_number=numbers[0], 
                                                              places=str([x[1] for x in links_locations_and_timestamps]), 
                                                              timestamps=str([x[2] for x in links_locations_and_timestamps]), 
                                                              locations=str(gps_coordinates)) 

  with open(username + "_instaloctrack_map.html", 'w') as f:
      f.write(outputText)
      f.close()
      print("Map with all the markers was written to: " + username + '_instaloctrack_map.html')


links = fetch_urls(number_publications)
browser.quit()
links_locations_and_timestamps = fetch_locations_and_timestamps(links)
gps_coordinates = geocode_all(links_locations_and_timestamps)
numbers = export_data(links_locations_and_timestamps, gps_coordinates)
map_locations()


