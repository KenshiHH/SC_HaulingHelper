from PIL import ImageGrab
import pytesseract
from flask import Flask
from flask import render_template, request
from flask import redirect
import uuid
import ctypes
import os
import re
from rapidfuzz import process, fuzz
import cv2
import numpy as np
from collections import Counter
import threading

####config
DEBUG = False
LOCALTEST = False


currentLocalScreenshot = 0

#get screen resolution
user32 = ctypes.windll.user32
screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)

#load json for ocr string fixes
import requests
import json
if DEBUG:
    with open('ocrfixes.json') as f:
        ocr_string_fixes = json.load(f)
    with open('known_locations.json') as f:
        known_locations = json.load(f)

else:
    ocr_string_fixes = json.loads(requests.get("https://github.com/KenshiHH/SC_HaulingHelper/raw/refs/heads/main/ocrfixes.json").text)
    known_locations = json.loads(requests.get("https://raw.githubusercontent.com/KenshiHH/SC_HaulingHelper/refs/heads/main/known_locations.json").text)



screenshot = None
OCR_Results = []

_ocr_lock = threading.Lock()

def split_containers(cargosize: int, max_size: int) -> list[int]:
    container_sizes = [32, 24, 16, 8, 4, 2, 1]
    """
    Packs `num_items` unit-sized items into available containers <= `max_size`.
    
    Returns list of used container sizes (e.g., [8, 2, 1] for 11 items, max 8).
    """
    remaining = cargosize
    used = []
    available = [s for s in container_sizes if s <= max_size]
    available.sort(reverse=True)
    
    for size in available:
        while remaining >= size:
            used.append(size)
            remaining -= size
        if remaining == 0:
            break    
    return used

class LocationCargo:
    def __init__(self,itemName:str):
        self.itemName = itemName
        self.container = []



def sortByCounter(cargolist:list):
    tmp = Counter(cargolist)
    sorted_list = sorted(tmp.items(), key=lambda x: x[0], reverse=True)
    return sorted_list



def fix_location(raw: str, threshold: int = 90) -> str:
    """
    Attempt to fix a location string by replacing known OCR errors with correct strings,
    and then trying to find a match in the known locations database.

    Args:
        raw (str): The original location string.
        threshold (int, optional): The minimum confidence required for a match to be considered.
            Defaults to 90.

    Returns:
        str: The fixed location string, or the original string if no confident match was found.
    """

    if raw not in known_locations:
        result = process.extractOne(raw, known_locations, scorer=fuzz.WRatio)
        if result and result[1] >= threshold:
            raw = result[0]
    
    for k in ocr_string_fixes:
        if k in raw:
            raw = raw.replace(k, ocr_string_fixes[k])

    return raw  # no  match keep original


# Set the path to tesseract.exe
script_dir = os.path.dirname(os.path.abspath(__file__))+"\\Tesseract-OCR"

pytesseract.pytesseract.tesseract_cmd = os.path.join(script_dir, 'tesseract.exe')
if not os.path.exists(os.path.join(script_dir, 'tesseract.exe')):
    raise Exception("tesseract.exe not found in path: "+script_dir)

app = Flask(__name__)

class LocationDatabase:
    class CargoDatabaseSplit:
        def __init__(self):
                # The core storage: { "LocationName": { "ItemName": ["Container1", "Container2"] } }
            self.data = {}

        def clear(self):
            self.data = {}


        def add_entry(self, location:str, item_name:str, container:int, max_container_size:int):
            """Adds a container to an item at a specific location."""
            tmp = split_containers(container, max_container_size)
            # check if location exists, if not create it
            if location not in self.data:
                self.data[location] = {}
            # check if item exists at location, if not create it
            if item_name not in self.data[location]:
                self.data[location][item_name] = []
            # add the container to the item at the location
            for i in tmp:
                self.data[location][item_name].append(i)


        def get_containers(self, location):
            ContainerList = []
            ContainerList.clear()
            for i in self.data[location]:
                self.data[location][i]
                tempCargo = []
                for j in self.data[location][i]:
                    tempCargo.append(j)
                data = Counter(tempCargo)
                sorted_output = sorted(data.items(), key=lambda x: x[0], reverse=True)
                for k in sorted_output:
                    ContainerList.append((i,k[0],k[1]))
                
            return ContainerList
        

        def __str__(self):
            """Returns a readable string version of the database."""
            return str(self.data)
        
        def getInfo(self):
            for i in self.data:
                print(f"Location: {i}")
                for j in self.data[i]:
                    print(f"  Item: {j}")
                    print(Counter(self.data[i][j]))

        def getLength(self, location):
            length = 0
            if location in self.data:
                return(len(self.data[location])) # get_containers 
            return length

    class Cargo:
        def __init__(self):
            self.itemName = ""
            self.SCUs = 0
            self.missionUUID = 0
            self.pickedUp = False
            self.droppedOff = False
            self.cargoList = []
    class DropLocation:
        def __init__(self):
            self.name = ""
            self.cargo = []
    class PickupLocation:
        def __init__(self):
            self.name = ""
            self.cargo = []

    def __init__(self):
        self.dropLocations = []
        self.pickupLocations = []
        self.locationList = []
        self.PickUpDatabase = self.CargoDatabaseSplit()
        self.DeliverDatabase = self.CargoDatabaseSplit()

    def AddPickupLocation(self, PickupLocation:str, Cargo: Cargo):
        bPickupLocationFound = False

        for i in self.pickupLocations:
            if PickupLocation == i.name:
                bPickupLocationFound = True
                i.cargo.append(Cargo)

        if not bPickupLocationFound:
            newPickupLocation = self.PickupLocation()
            newPickupLocation.name = PickupLocation
            newPickupLocation.cargo.append(Cargo)
            self.pickupLocations.append(newPickupLocation)

    def AddDropLocation(self, Drop :str, Cargo: Cargo):
        bDropLocationFound = False

        for i in self.dropLocations:
            if Drop == i.name:
                bDropLocationFound = True
                i.cargo.append(Cargo)

        if not bDropLocationFound:
            newDropLocation = self.DropLocation()
            newDropLocation.name = Drop
            newDropLocation.cargo.append(Cargo)
            self.dropLocations.append(newDropLocation)

    def GetPickupLocations(self):
        return self.pickupLocations
    
    def GetDropLocations(self):
        return self.dropLocations
    
    def GenerateLocationList(self,location: str):
        bfound = False
        locationDetail = {}
        locationDetail["name"] = location
        locationDetail["order"] = len(self.locationList)+1
        locationDetail["done"] = False


        for i in self.locationList:
            if i["name"] == location:
                bfound = True
        if not bfound:
            self.locationList.append(locationDetail)

    def ReorderLocationList(self,new_order):
        newOrder = []
        for i in new_order:
            newOrder.append(self.locationList[int(i)-1])
        self.locationList = newOrder
        for i in self.locationList:
            i["order"] = self.locationList.index(i)+1

    def GenerateDropPickupList(self, missionDatabase, bGenerate:bool = False):
        if not bGenerate:
            if missionDatabase.locationDatabase.locationList:
                return
        self.locationList.clear()
        self.pickupLocations.clear()
        self.dropLocations.clear()
        for i in missionDatabase.mainMissions:
            for j in i.subMissions:
                pickupCargo = LocationDatabase.Cargo()
                pickupCargo.itemName = j.item
                pickupCargo.SCUs = j.scu
                pickupCargo.missionUUID = i.uuid
                missionDatabase.locationDatabase.AddPickupLocation(j.pickupLocation, pickupCargo)
                self.GenerateLocationList(j.pickupLocation)
                for k in j.dropLocations:
                    cargo = LocationDatabase.Cargo()
                    cargo.itemName = j.item
                    cargo.SCUs = k['SCU']
                    cargo.missionUUID = i.uuid
                    missionDatabase.locationDatabase.AddDropLocation(k['DropLocation'], cargo)
                    self.GenerateLocationList(k['DropLocation'])

    def GetPickupList(self,location:str):
        self.PickUpDatabase.clear()
        for i in self.pickupLocations:
            if i.name == location:
                result = i.cargo
                for k in result:
                    self.PickUpDatabase.add_entry(location=location, item_name=k.itemName, container=k.SCUs, max_container_size=missionDatabase.GetMaxContainerSizebyUuid(k.missionUUID))
        try:
            temp = self.PickUpDatabase.get_containers(location)
        except:
            return []
        return temp

            
    def GetDropList(self,location:str):
        self.DeliverDatabase.clear()
        for i in self.dropLocations:
            if i.name == location:
                result = i.cargo
                for k in result:
                    self.DeliverDatabase.add_entry(location=location, item_name=k.itemName, container=k.SCUs, max_container_size=missionDatabase.GetMaxContainerSizebyUuid(k.missionUUID))
        try:
            temp = self.DeliverDatabase.get_containers(location)
        except:
            return []
        return temp

    def GetCargoTab3(self,location:str):
        global missionDatabase
        pickupCargo = self.GetPickupList(location)
        dropCargo = self.GetDropList(location)
        template = ["","","",""]
        listenarray :list = []

        maxLength = max(len(pickupCargo), len(dropCargo))

        for i in range(maxLength):
            try:
                if i < len(pickupCargo):
                    template[0] = f"{pickupCargo[i][2]}x {pickupCargo[i][1]}scu - " 
                    template[1] = f"{pickupCargo[i][0]}" 
                else:
                    template[0] = ""
                    template[1] = ""
            except:
                    template[0] = ""
                    template[1] = ""
            try:
                if i < len(dropCargo):
                    template[2] = f"{dropCargo[i][2]}x {dropCargo[i][1]}scu - "  
                    template[3] = f"{dropCargo[i][0]}" 
                else:
                    template[2] = ""
                    template[3] = ""
            except:
                    template[0] = ""
                    template[1] = ""
            listenarray.append(template)
            template = ["","","",""]
        return listenarray
    
    def ToggleLocationStatus(self,location: str):
        for i in self.locationList:
            if i["name"] == location:
                i["done"] = not i["done"]


class SortedMission:
    def __init__(self):
        self.dropOfLocation = ""
        self.cargo = []

class SortedMissionManager:

    def __init__(self):
        self.sortedMissions: SortedMission = []

    def AddSortedMissions(self,DropLocation:str, SCU:int, Item:str, MissionID:int):
        bDropLocationFound = False

        for i in self.sortedMissions:
                if DropLocation == i.dropOfLocation:
                    bDropLocationFound = True
                    i.cargo.append([SCU,Item,MissionID])

        if not bDropLocationFound:
            newSortedMissions = SortedMission()
            newSortedMissions.dropOfLocation = DropLocation
            newSortedMissions.cargo.append([SCU,Item,MissionID])
            self.sortedMissions.append(newSortedMissions)

    def CheckForMissions(self):
        global missionDatabase
        self.sortedMissions.clear()

        for i in missionDatabase.mainMissions:
            for j in i.subMissions:
                for k in j.dropLocations:
                    self.AddSortedMissions(k['DropLocation'], k['SCU'], j.item,i.missionID)

        self.sortedMissions.sort(key=lambda x: x.dropOfLocation) # Sort by Drop Location Name

class SubMission:
    def __init__(self):
        self.item = ""
        self.scu = 0
        self.pickupLocation = ""
        self.dropLocations = []
        self.pickupInfo = {
            "Item": "",
            "PickupLocation": ""
        }

    def AddPickupInfo(self, Item:str, PickupLocation:str):
        self.item = Item
        self.pickupLocation = PickupLocation

    def AddDropLocation(self,Item:str, SCU:int, DropLocation:str):
        subMissionDetails = {
        "Item" : Item,
        "SCU" : SCU,
        "DropLocation": DropLocation}
        self.dropLocations.append(subMissionDetails)

    def GetMissionText(self):
        return f"{self.item} from {self.pickupLocation}"


class MainMission:
    def __init__(self):
        self.subMissions: SubMission = []
        self.missionID = 0
        self.sortedID = 0
        self.auec = 0
        self.uuid = uuid.uuid4()
        self.maxContainerSize = 0

    def AddSubMission(self, subMission: SubMission):
        self.subMissions.append(subMission)

    def GetID(self):
        return str(self.missionID)
    
    def GetUEC(self):
        return self.auec


class MissionDatabase:
    def __init__(self):
        self.mainMissions: MainMission = []
        self.cargoSCU = 0
        self.sortedMissionManager = SortedMissionManager()
        self.dropOffLocations = {}
        self.pickupLocations = {}
        self.auec = 0
        self.locationDatabase = LocationDatabase()

    def GetMaxContainerSizebyUuid(self,uuid):
        for mission in self.mainMissions:
            if mission.uuid == uuid:
                return mission.maxContainerSize
        return 0

    def AddMainMission(self, mainMission: MainMission):
        self.mainMissions.append(mainMission)
        self.UpdateMissionIDs()
        self.UpdateCargoSCU()
        self.UpdateAUEC()
        print(f"max container size: {mainMission.maxContainerSize}")

    def UpdateMissionIDs(self):
        for i in self.mainMissions:
            i.missionID = self.mainMissions.index(i)+1
            
    def UpdateCargoSCU(self):
        self.cargoSCU = 0
        for i in self.mainMissions:
            for j in i.subMissions:
                for k in j.dropLocations:
                    self.cargoSCU += k['SCU']

    def UpdateAUEC(self):
        self.auec = 0
        for i in self.mainMissions:
            self.auec += i.auec

    def GetAuec(self):
        auec = self.auec
        auec = "{:,}".format(auec).replace(",", ".")
        return auec

    def GetCargoSCU(self):
        return self.cargoSCU

    def EditMissionReward(self,missionID:int,reward:int):
        self.mainMissions[int(missionID)-1].auec = reward
        self.UpdateAUEC()

    def RemoveMainMission(self,int):
        try:
            del self.mainMissions[int-1]
        except:
            print("error deleting Mission"+str(int))
        self.UpdateMissionIDs()
        self.UpdateCargoSCU()
        self.UpdateAUEC()

    def newMissionOrder(self,new_order):
        newOrder: MainMission = []
        newOrder.clear()
        for i in new_order:
            newOrder.append(self.mainMissions[int(i)-1])
        self.mainMissions.clear()
        self.mainMissions = newOrder 
        self.UpdateMissionIDs()

    def GeneratePickupLocations(self):
        self.pickupLocations.clear()
        for i in self.mainMissions:
            for j in i.subMissions:
                self.pickupLocations[j.pickupLocation] = 0                     

missionDatabase = MissionDatabase()

def ExtractReward():
    reward = 0
    global screenshot
    global OCR_Results
    
    text = OCR_Results[1]
    if DEBUG:
        print(text)
    text = text.split('\n')

    print(text)
    try:
        for i in text:
            if "reward" in i.lower():
                rew = i.rsplit(' ', 1)[-1]
                rew = rew.replace(",", "")
                reward = int(rew)
    except:
        print("reward not found")
        pass

    return reward

def ExtractMaxContainerSize():
    global OCR_Results
    num = 0    
    #cv2.imwrite('test.jpg', screenshot_containerInfo)
    #text = pytesseract.image_to_string(screenshot_containerInfo,config=custom_config)
    text = OCR_Results[2]
    text = text.replace('©', '')
    text = text.replace('\n', '')
    text = text.rsplit('SCU', 1)[0]
    text = text[-4:].strip()
    num = re.search(r'\d+', text).group(0) if text else None
    return int(num)

def _ocr_worker(image, index: int):
    blacklist_chars = '!@#$%^&*()_+-=[]{}|;\'"<>?~`\\¬¦'
    game_icons = '◇◆□■○●'
    custom_config = f'--oem 3 --psm 6 -c tessedit_char_blacklist={blacklist_chars}{game_icons}'
    """Run tesseract on one image crop and store result at the correct index."""
    result = pytesseract.image_to_string(image, config=custom_config)
    with _ocr_lock:
        while len(OCR_Results) <= index:
            OCR_Results.append("")
        OCR_Results[index] = result


def CreateOcrText():
    global screenshot, OCR_Results

    extract_mission_coords = (
        screen_width * 0.62, screen_height * 0.25,
        screen_width * 0.90, screen_height * 0.70,
    )
    auec_coords = (
        screen_width * 0.66, screen_height * 0.10,
        screen_width * 0.95, screen_height * 0.26,
    )
    container_coords = (
        screen_width * 0.34, screen_height * 0.26,
        screen_width * 0.62, screen_height * 0.76,
    )
    coord_list = [extract_mission_coords, auec_coords, container_coords]

    OCR_Results.clear()

    if LOCALTEST:
        global currentLocalScreenshot
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, '4_7', f'test_{currentLocalScreenshot}.png')
        screenshot = cv2.imread(image_path)
    else:
        screenshot = np.array(ImageGrab.grab())

    screen_list = []
    for c in coord_list:
        crop = screenshot[int(c[1]):int(c[3]), int(c[0]):int(c[2])]
        screen_list.append(crop)

    processed = []
    for idx, img in enumerate(screen_list):
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        if idx == 1:
            img = cv2.threshold(img, 110, 255, cv2.THRESH_BINARY)[1]
        img = cv2.bitwise_not(img)
        if LOCALTEST:
            cv2.imwrite(f"test{idx}.jpg", img)
        processed.append(img)

    threads = [
        threading.Thread(target=_ocr_worker, args=(processed[i], i))
        for i in range(len(processed))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def ExtractMissionInfo():
    global missionDatabase
    global custom_config
    global screenshot
    global OCR_Results

    text = OCR_Results[0]
    text = text.replace('©', '')
    
    if DEBUG:
        print("OCR Text:")
        print(text)
        print("---END---")

    text = re.sub(r'PRIMARY OBJECTIVES\s*\n', '', text)
    text = re.sub(r'[^\w\s\n./\-]+\s*(?=Deliver)', '', text)
    text = re.sub(r'[\|\s]+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?<!\.)(\n)(?=[A-Z][a-z])', ' ', text)
    ocrArray = re.split(r'(?=Deliver)', text)
    ocrArray = [p.strip() for p in ocrArray if p.strip()]

    newMission = MainMission()

    try:
        for i in ocrArray:
            newSubMission = SubMission()
            PATTERN = re.compile(
                r'Deliver \d+/(?P<scu>\d+) SCU of (?P<cargo>[\w\s]+?) to (?P<deliver_target>.+?)\.'
                r'.*?'
                r'Collect [\w\s]+? from (?P<collect_from>.+?)(?:\.|$)',
                re.DOTALL
            )
            m = PATTERN.search(i)
            if m:
                scu    = int(m.group('scu'))            # 3
                cargo    = m.group('cargo')                 # "Corundum"
                target = m.group('deliver_target')      # "Teasa Spaceport in Lorville"
                pickup = m.group('collect_from')        # "Everus Harbor"
            
            target = fix_location(target)
            pickup = fix_location(pickup)
            if DEBUG:
                print(f"Extracted: \n{scu} SCU \n{cargo} \nto {target}\ncollect from {pickup}")
            newSubMission.scu += int(scu)
            newSubMission.AddPickupInfo(cargo, pickup)
            newSubMission.AddDropLocation(cargo,int(scu), target)
            newMission.AddSubMission(newSubMission)
            newMission.auec = ExtractReward()
        newMission.maxContainerSize = ExtractMaxContainerSize()
        missionDatabase.AddMainMission(newMission)
            
    except Exception as error:
        print("Error extracting mission info")
        print("An exception occurred:", error)

@app.route('/')
def index():
    return render_template('index.html', missionDatabase=missionDatabase)

@app.route('/edit/<id>/<auec>', methods=['PUT'])
def editReward(id,auec):
    print("editreward",id,auec)
    missionDatabase.EditMissionReward(int(id),int(auec))
    return render_template('tab1.html', missionDatabase=missionDatabase)

@app.route('/delete/<id>', methods=['DELETE'])
def delete(id):
    missionDatabase.RemoveMainMission(int(id))
    missionDatabase.sortedMissionManager.CheckForMissions()
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase,True)
    return render_template('tab1.html', missionDatabase=missionDatabase)

@app.route('/add/', methods=['POST'])
def AddMission():
    global currentLocalScreenshot
    if LOCALTEST:
        currentLocalScreenshot += 1
    CreateOcrText()
    ExtractMissionInfo()
    missionDatabase.sortedMissionManager.CheckForMissions()
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase,True)
    return redirect("/")

@app.route('/toggle/<location>', methods=['POST'])
def ToggleLocation(location):
    missionDatabase.locationDatabase.ToggleLocationStatus(location)
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('route.html', missionDatabase=missionDatabase)

@app.route('/update-order', methods=['POST'])
def update_order():
    new_order = request.json.get('order', [])
    if DEBUG:
        print("Neue Sortierung:", new_order)
    missionDatabase.locationDatabase.ReorderLocationList(new_order)
    return render_template('route.html', missionDatabase=missionDatabase)

@app.route('/route', methods=['GET'])
def route():
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('route.html', missionDatabase=missionDatabase)

@app.route('/stations', methods=['POST'])
def stations():
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('stations.html', missionDatabase=missionDatabase)

@app.route('/tab1', methods=['GET'])
def tab1():
    return render_template('tab1.html', missionDatabase=missionDatabase)

@app.route('/tab2', methods=['GET'])
def tab2():
    missionDatabase.sortedMissionManager.CheckForMissions()
    return render_template('tab2.html', missionDatabase=missionDatabase)

@app.route('/tab3', methods=['GET'])
def tab3():
    missionDatabase.locationDatabase.GenerateDropPickupList(missionDatabase)
    return render_template('tab3.html', missionDatabase=missionDatabase)



if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')