#!/usr/bin/env python
# coding: utf-8

# In[1]:
import pandas as pd
import numpy as np
import geopy.distance
from ship import current_speed
from ship import speedloss
from BeaufortNumber import beaufort_scale
import matplotlib.pyplot as plt
import numpy as np
import requests


url = "https://stormglass.p.rapidapi.com/forecast"
headers = {
	"X-RapidAPI-Key": "7e5b4269bfmshc55d8eacc1f6c34p1e6037jsna62e35c6a177",
	"X-RapidAPI-Host": "stormglass.p.rapidapi.com"
}

def round_one(number):
    value = float("{0:.1f}".format(number))
    return value
#How to get data of ship routes from file
def Data(excel_name):
    xls = pd.ExcelFile(excel_name)
    # to read all sheets to a map
    ship_route = {}
    for sheet_name in xls.sheet_names:
        ship_route[sheet_name] = xls.parse(sheet_name, usecols=[1,2])
        # can also use sheet_index [0,1,2..] instead of sheet name.
    for route in ship_route.values():
        route.columns = ['lat1','lon1']    
    return ship_route

def new_ship_route(route):
    new_route = route.copy()
    lat2 = new_route['lat1']
    lat2 = lat2.drop(labels=[0], axis=0)
    lat2.loc[len(lat2.index)+1] = np.NaN
    lat2 = lat2.reset_index(drop=True)
    lon2 = new_route['lon1']
    lon2 = lon2.drop(labels=[0], axis=0)
    lon2.loc[len(lon2.index)+1] = np.NaN
    lon2 = lon2.reset_index(drop=True)
    new_route.insert(2, 'lat2', lat2)
    new_route.insert(3, 'lon2', lon2)
    new_route = new_route.drop(labels=[len(route)-1])
    return new_route

def distance(lat1, lon1, lat2, lon2):
    coords_1 = (lat1, lon1)
    coords_2 = (lat2, lon2)
    estimate = geopy.distance.geodesic(coords_1, coords_2).km
    return estimate

def wave_list(route, displacement, speed, ship_type, start_time):
    time = start_time
    wave_height_list = []
    beaufort_number_list = []
    speed_list = []
    time_list = []
    for latitude, longitude, distance in zip(route['lat1'], route['lon1'], route['distance (km)']):
        wave_height_list.append(round_one(wave_height(str(latitude), str(longitude), time)))
        beaufort_number_list.append(beaufort_number(wave_height_list[len(wave_height_list)-1]))
        speed_list.append(current_speed(beaufort_number_list[len(beaufort_number_list)-1], displacement, speed, ship_type)*0.514)
        time_list.append(sail_time(distance, speed_list[len(speed_list)-1]))
        time = time + int(time_list[len(time_list)-1])
    return wave_height_list

#V akhir (t=x/v)
# misalkan wave height diketahui maka dapat dikategorikan ke salah satu list
def beaufort_number(wave):
    BN = 0
    for x in beaufort_scale['Wave Height']:
        if wave == 0:
            break
        elif wave not in x:
            BN += 1
        elif wave in x:
            break    
    return BN

def route(route_name, Data, displacement, speed, ship_type, BHP, sfoc, start_time):    
    route = Data[route_name]
    new_route = new_ship_route(route)
    use_route = distance_route(new_route, displacement, speed, ship_type, BHP, sfoc, start_time)
    return use_route

def sail_time(distance, speed):
    second = distance*1000/speed #time in second
    minute = second/60 #time in minute
    hour = minute/60 #time in hour
    return hour

def foc(time, BHP, sfoc):
    fuel = time*sfoc*BHP
    fuel_ton = fuel/(10**6)
    return fuel_ton

def wave_height(lat, lng, time):
    querystring = {"lat":lat,"lng":lng}
    response = requests.request("GET", url, headers=headers, params=querystring)
    result = response.json()
    i = 0
    for value in result['hours']:
        for item in value['waveHeight']:
            if item['source'] == 'meteo':
                i += 1
                if i == time:
                    wave_value = item['value']
                break
            elif item['source'] == 'sg':
                i += 1
                if i == time:
                    wave_value = item['value']
    return wave_value
    
def distance_route(route, displacement, speed, ship_type, BHP, sfoc, start_time):
    knot = 0.514 #m/s
    route['distance (km)'] = route.apply(lambda row : distance(row['lat1'],
                                row['lon1'], row['lat2'], row['lon2']), axis=1)
    route['wave (m)'] = wave_list(route, displacement, speed, ship_type, start_time)
    route['BN'] = route.apply(lambda row: beaufort_number(row['wave (m)']), axis=1)
    route['speedloss (%)'] = route.apply(lambda row: speedloss(row['BN'], displacement, ship_type), axis=1)
    route['speed (m/s)'] = route.apply(lambda row: current_speed(row['BN'], displacement, speed*knot, ship_type), axis=1)
    route['time (hour)'] = route.apply(lambda row: sail_time(row['distance (km)'],
                                row['speed (m/s)']), axis=1)
    route['foc (ton)'] = route.apply(lambda row: foc(row['time (hour)'], BHP, sfoc), axis=1)
    return route

def estimate(route_name, Data, displacement, speed, ship_type, BHP, sfoc, start_time):
    route_used = route(route_name, Data, displacement, speed, ship_type, BHP, sfoc, start_time)
    total = {}
    path = {route_name : total}
    total_distance = route_used['distance (km)'].sum(axis=0)
    total_hour = route_used['time (hour)'].sum(axis=0)
    total_foc = route_used['foc (ton)'].sum(axis=0)
    total['total distance (km)'] = total_distance
    total['total sailing time (hour)'] = total_hour
    total['total foc (ton)'] = total_foc
    return path
    
def ratio(dataratio):
    data = dataratio.copy()
    distance = data['total distance (km)']
    foc = data['total foc (ton)']
    max_value_distance = data['total distance (km)'].max()
    max_value_foc = data['total foc (ton)'].max()
    ratio_distance = (distance/max_value_distance)*100
    ratio_foc = (foc/max_value_foc)*100
    data.insert(1, 'ratio distance (%)', ratio_distance)
    data.insert(4, 'ratio foc (%)', ratio_foc)
    return data

def estimateall(Data, displacement, speed, ship_type, BHP, sfoc, start_time):
    all_total_estimation = {}
    for key in Data:
        all_total_estimation.update(estimate(key, Data, displacement, speed, ship_type, BHP, sfoc, start_time))
    df = pd.DataFrame.from_dict(all_total_estimation, orient = 'index')
    return df

def dec_making(data, route1, route2, route3, route4, Lpp):
    for value in route1['wave (m)']:
        if value <= 0.04*Lpp:
           continue
        else:
            print('hindari jalur 1 karena tinggi gelombang melebihi 0.04Lpp')
    for value in route2['wave (m)']:
        if value <= 0.04*Lpp:
           continue
        else:
            print('hindari jalur 2 karena tinggi gelombang melebihi 0.04Lpp')  
    for value in route3['wave (m)']:
        if value <= 0.04*Lpp:
           continue
        else:
            print('hindari jalur 3 karena tinggi gelombang melebihi 0.04Lpp')  
    for value in route4['wave (m)']:
        if value <= 0.04*Lpp:
           continue
        else:
            print('hindari jalur 4 karena tinggi gelombang melebihi 0.04Lpp')                   
    min_value = data['total foc (ton)'].idxmin()
    call = 'Jalur pelayaran dengan konsumsi bahan bakar paling minimum adalah {}'.format(min_value)
    return print(call)
        
###this function works to save data###
def save(data, filename):
    data.to_csv(filename)

###graph###
###this function works to visualize the data
def total_foc(route):
    list_foc = []
    x = 0
    for foc in route['foc (ton)']:
        x += foc
        list_foc.append(x)
    return list_foc

def total_distance(route):
    list_distance = []
    x = 0
    for distance in route['distance (km)']:
        x += distance
        list_distance.append(x)
    return list_distance

def sailing_time(route):
    list_time = []
    x = 0
    for time in route['time (hour)']:
        x += time
        list_time.append(x)
    return list_time

#function to make foc_graph
def foc_graph(route1, route2, route3, route4):
    fig, ax = plt.subplots(figsize=(10, 5)) 
    x1 = total_distance(route1)
    x2 = total_distance(route2)
    x3 = total_distance(route3)
    x4 = total_distance(route4)
    y1 = total_foc(route1)
    y2 = total_foc(route2)
    y3 = total_foc(route3)
    y4 = total_foc(route4)
    # Define x and y axes
    ax.plot(x1, y1, color='cyan', label='Jalur 1', linewidth=2, linestyle='-', marker ='o')  # plot first line
    ax.plot(x2, y2, color='red', label='Jalur 2', linewidth=2, linestyle='--', marker ='o')  # plot second line
    ax.plot(x3, y3, color='yellow', label='Jalur 3', linewidth=2, linestyle='-.', marker='o')  # plot third line
    ax.plot(x4, y4, color = 'green', label = 'Jalur 4', linewidth=2, linestyle=':',marker='o')  # plot fourth line
    # Set plot title and axes labels
    ax.set_title("Fuel oil Consumption", fontsize=15)
    ax.set_xlabel("Sailing Distance (km)", fontsize=12)
    ax.set_ylabel("Fuel oil Consumption (ton)", fontsize=12)
    plt.legend()
    plt.show()

def foc_graph_finish(route1, route2, route3, route4):
    fig, ax = plt.subplots(figsize=(10, 5)) 
    x1 = total_distance(route1)
    x2 = total_distance(route2)
    x3 = total_distance(route3)
    x4 = total_distance(route4)
    y1 = total_foc(route1)
    y2 = total_foc(route2)
    y3 = total_foc(route3)
    y4 = total_foc(route4)
    # Define x and y axes
    ax.plot(x1, y1, color='cyan', label='Jalur 1', linewidth=2, linestyle='-', marker ='o')  # plot first line
    ax.plot(x2, y2, color='red', label='Jalur 2', linewidth=2, linestyle='--', marker ='o')  # plot second line
    ax.plot(x3, y3, color='yellow', label='Jalur 3', linewidth=2, linestyle='-.', marker='o')  # plot third line
    ax.plot(x4, y4, color = 'green', label = 'Jalur 4', linewidth=2, linestyle=':',marker='o')  # plot fourth line
    # Set plot title and axes labels
    ax.set_title("Fuel oil Consumption", fontsize=15)
    ax.set_xlabel("Sailing Distance (km)", fontsize=12)
    ax.set_ylabel("Fuel oil Consumption (ton)", fontsize=12)
    plt.ylim([12.5,20])
    plt.xlim([1200,1550])
    plt.legend()
    plt.show()
    
#function to make speedloss graph
def speed_loss_graph(route1, route2, route3, route4):
    fig, ax = plt.subplots(figsize=(10, 5)) #ini untuk ukuran gambarnya
    x1 = total_distance(route1)
    x2 = total_distance(route2)
    x3 = total_distance(route3)
    x4 = total_distance(route4)
    y1 = route1['speedloss (%)']
    y2 = route2['speedloss (%)']
    y3 = route3['speedloss (%)']
    y4 = route4['speedloss (%)']
    # Define x and y axes
    ax.plot(x1, y1, color='cyan', label='Jalur 1', linewidth=2, linestyle='-', marker='o')  # plot first line
    ax.plot(x2, y2, color='red', label='Jalur 2', linewidth=2, linestyle='--', marker='o')  # plot second line
    ax.plot(x3, y3, color='yellow', label='Jalur 3', linewidth=2, linestyle='-.', marker='o')  # plot third line
    ax.plot(x4, y4, color = 'green', label = 'Jalur 4', linewidth=2, linestyle=':', marker='o')  # plot fourth line
    # Set plot title and axes labels
    ax.set_title("Percentage of Speed Loss", fontsize=15)
    ax.set_xlabel("Sailing Distance (km)", fontsize=12)
    ax.set_ylabel("Speed Loss (%)", fontsize=12)
    plt.legend()
    plt.show()

#function to make sailing time graph
def sailing_time_graph(route1, route2, route3, route4):
    # Define plot space
    fig, ax = plt.subplots(figsize=(10, 5)) #ini untuk ukuran gambarnya
    x1 = total_distance(route1)
    x2 = total_distance(route2)
    x3 = total_distance(route3)
    x4 = total_distance(route4)
    y1 = sailing_time(route1)
    y2 = sailing_time(route2)
    y3 = sailing_time(route3)
    y4 = sailing_time(route4)
    # Define x and y axes
    ax.plot(x1, y1, color='cyan', label='Jalur 1', linewidth=2, linestyle='-', marker='o')  # plot first line
    ax.plot(x2, y2, color='red', label='Jalur 2', linewidth=2, linestyle='--', marker='o')  # plot second line
    ax.plot(x3, y3, color='yellow', label='Jalur 3', linewidth=2, linestyle='-.', marker='o')  # plot third line
    ax.plot(x4, y4, color = 'green', label = 'Jalur 4', linewidth=2, linestyle=':', marker='o')  # plot fourth line
    # Set plot title and axes labels
    ax.set_title("Sailing Time", fontsize=15) #ini ganti judul grafiknya yg diatas bisa aja dikosongin
    ax.set_xlabel("Sailing Distance (km)", fontsize=12)
    ax.set_ylabel("Sailing Time (hour)", fontsize=12) # ini untuk buat label y nya
    plt.legend()
    plt.show()

def sailing_time_graph_finish(route1, route2, route3, route4):
    # Define plot space
    fig, ax = plt.subplots(figsize=(10, 5)) #ini untuk ukuran gambarnya
    x1 = total_distance(route1)
    x2 = total_distance(route2)
    x3 = total_distance(route3)
    x4 = total_distance(route4)
    y1 = sailing_time(route1)
    y2 = sailing_time(route2)
    y3 = sailing_time(route3)
    y4 = sailing_time(route4)
    # Define x and y axes
    ax.plot(x1, y1, color='cyan', label='Jalur 1', linewidth=2, linestyle='-', marker='o')  # plot first line
    ax.plot(x2, y2, color='red', label='Jalur 2', linewidth=2, linestyle='--', marker='o')  # plot second line
    ax.plot(x3, y3, color='yellow', label='Jalur 3', linewidth=2, linestyle='-.', marker='o')  # plot third line
    ax.plot(x4, y4, color = 'green', label = 'Jalur 4', linewidth=2, linestyle=':', marker='o')  # plot fourth line
    # Set plot title and axes labels
    ax.set_title("Sailing Time", fontsize=15) #ini ganti judul grafiknya yg diatas bisa aja dikosongin
    ax.set_xlabel("Sailing Distance (km)", fontsize=12)
    ax.set_ylabel("Sailing Time (hour)", fontsize=12) # ini untuk buat label y nya
    plt.ylim([40,80])
    plt.xlim([1200,1550])
    plt.legend()
    plt.show()
    
def total_foc_graph(data):
    x = data.index.format()
    y = data['total foc (ton)']
    fig = plt.figure(figsize = (5, 5))
    # creating the bar plot
    plt.bar(x, y, color ='red')
    plt.ylabel("FOC (ton)", fontsize=10)
    plt.title("Total Fuel Oil Consumption from Different Route", fontsize=12)
    plt.show()
    