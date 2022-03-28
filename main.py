import logging
logging.basicConfig(filename='output.log', encoding='utf-8', level=logging.INFO)
try:
    from ics import Calendar
    from todoist.api import TodoistAPI
    import requests
    import arrow
    import configparser
except Exception as e:
    logging.error(e)
    print("An error Occured Exiting...")
    exit()

#https://www.programiz.com/python-programming/datetime/strftime
#https://strftime.org/

#start_time = datetime.datetime.now()
timezone = "US/Eastern"
start_time=arrow.utcnow().to(timezone)

# For times
# https://arrow.readthedocs.io/en/latest/#supported-tokens
arrow.utcnow().strftime("%m/%d/%Y %I:%M%p")
formats = ["M/D/YYYY, h:mm A","YYYY-MM-DD HH:mm"]
#DESCRIPTION
completed = []



def get_todoist_projects(api):
    output = {}
    for project in api.projects.all():
        output[project["name"]] = project["id"]
    return output



# Get Deduped list of events from a calendar object
def get_cal_events(url):
    cal = Calendar(requests.get(url).text)
    event_names = []
    final_list = []
    for e in cal.timeline:
        event_names.append(e.name)

    for e in cal.timeline:
        event = ""
        if "Availability Ends" not in e.name:
            e.name = e.name
            event = e
        # If an event has an "Availability Ends" but not a due
        elif "Availability Ends" in e.name and e.name.replace("Availability Ends", "Due") not in event_names:
            e.name = e.name.replace(" - Availability Ends", " - Due")
            event = e

        if type(event) != str and start_time < event.begin:
            e.begin = e.begin.to(timezone) # Convert all our start times to Eastern
            #time = e.begin.strftime("%m/%d/%Y %I:%M%p")
            time = e.begin.format(formats[0])
            final_list.append((e.name,time,e.description))
    return final_list
    #print(f"{len(event_names)} total events were found")
    #print(f"There are {len(final_list)} valid events after deduping and removing already past events")

#Get the id of the Automated Tag
def get_auto_label(api):
    for label in api.labels.all():
        if label["name"] == "Automated":
            return label["id"]

def get_todoist_items(project_id, api):
    #2022-01-27 23:59
    names = []
    times = []
    items = []
    for item in api.projects.get_data(project_id)["items"]:
        if item["labels"] == get_auto_label(api):
            #date = arrow.get(item["due"]["string"], formats).strftime("%m/%d/%Y %I:%M%p")
            date = arrow.get(item["due"]["string"], formats).format(formats[0])
            name = item["content"]
            names.append(name)
            times.append(date)
            items.append(item)
    return names,times, items


def process_lists(ics, todoist, id, api):
    names, times, items = todoist
    for name, time, description in ics:
        try:
            index = names.index(name)
        except ValueError:
            index = -1
        if index != -1:
            if start_time > arrow.get(times[index], formats):
                logging.info(f"{name} Time Passed \t|\t No Action Needed")
            elif times[index] == time:
                logging.info(f"{name}\t|\t No Action Needed")
            else:
                logging.info(f"{name} set time doesn't match \t|\t will update id {items[index]['id']} ")
                new_date = {
                "date": None,
                "timezone": None,
                "string": time,
                "lang": "en",
                "is_recurring": False
                }
                api.items.get_by_id(items[index]["id"]).update(due=new_date)
                #items[index]
                #print()
        elif name in get_completed(api):
            logging.info(f"{name} already completed \t|\t No Action Needed")
        else:
            logging.info(f"{name} is not in content \t|\t Will add to list")
            due_date = {
            "date": None,
            "timezone": None,
            "string": time,
            "lang": "en",
            "is_recurring": False
            }
            item = api.items.add(name, labels=get_auto_label(api), due=due_date, auto_reminder=True, project_id=id)
            note = api.notes.add(item["id"], description)

#Get a list of completed items so they won't be added again
def get_completed(api):
    global completed
    if completed == []:
        for item in api.completed.get_all()["items"]:
            completed.append(item["content"].replace(" @Automated",""))
        return completed
    else:
        return completed

# Update a given config's items
def process_account(api_key, links):
    api = TodoistAPI(api_key)
    api.sync()
    projects = get_todoist_projects(api)
    for key in links:
        items = get_todoist_items(projects[key], api)
        if items == ([], [], []): # If there aren't any items currently listed
            continue
        events = get_cal_events(links[key])
        process_lists(events, items , projects[key],api)
        print("Finished Processing")
    api.commit()
    print("Finished Updating")

def main():
    config = configparser.RawConfigParser()
    config.optionxform=str # Keep capitalization
    config.read("config.ini")
    users = {s:dict(config.items(s)) for s in config.sections()}
    for key in users:
        process_account(key, users[key])
#print()


try:
    main()
except Exception as e:
    logging.error(e)
#api.commit()
#print("--------------------------------------")


#print("Event '{}' started {}".format(e.name, e.begin.humanize()))
