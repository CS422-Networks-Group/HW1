import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import requests
import socket
import ipaddress
import subprocess
import IP2Location  
import os
from tqdm import tqdm
import threading

#check whether a value is an ip address or a host name
def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

def process_csv(csv_file: str) -> pd.DataFrame:
    #read the csv
    df = pd.read_csv(csv_file)

    database = IP2Location.IP2Location(os.path.join("data", "IP2LOCATION-LITE-DB5.BIN"))

    #initialize two new columns
    df["LATITUDE"] = None
    df["LONGITUDE"] = None
    
    #read each row in csv and obtain the latitude and longitude
    for index, row in df.iterrows():
        ip_or_host = row["IP/HOST"]
        valid_ip = True
        if not is_ip_address(ip_or_host):
            
            #TODO: n    eed to add our computer's ip addresses when the script is ran
            try:
                ip_or_host = socket.gethostbyname(ip_or_host)
            except socket.gaierror:
                valid_ip = False
        if valid_ip:
            response = database.get_all(ip_or_host) 
            #setting the df values
            df.loc[index, "IP/HOST"] = ip_or_host
            df.loc[index, "LONGITUDE"] = response.latitude
            df.loc[index, "LATITUDE"] = response.longitude
        
        #for now, drop the rows whose latitude and longitutde fields are empty
    filtered_df = df[df["LATITUDE"].notna() & df["LONGITUDE"].notna()]

    return filtered_df


def execute_ping_tests(df: pd.DataFrame, start: int, end: int):
    for _, row in df.iloc[start:end+1].iterrows():
        res = subprocess.run(
            ["ping", "-c", "11", row["IP/HOST"]],
            capture_output=True,
            text=True
        )
        print(res.stdout)
def main():
    '''
    basic flow: read the csv

    then populate it with geographical data (include new columns for lat and longitude)

    update the csv

    run the ping tests

    capture the data 

    plot it
    '''
    df = process_csv("data/listed_iperf3_servers.csv")
    thread1 = threading.Thread(target=execute_ping_tests, args=(df, 0, 37))
    thread2 = threading.Thread(target=execute_ping_tests, args=(df, 38, 75))
    thread3 = threading.Thread(target=execute_ping_tests, args=(df, 76, 113))
    thread4 = threading.Thread(target=execute_ping_tests, args=(df, 114, 151))
    thread5 = threading.Thread(target=execute_ping_tests, args=(df, 152, 188))

    thread1.start()
    thread2.start()
    thread3.start()
    thread4.start()
    thread5.start()

    thread1.join()
    thread2.join()
    thread3.join()
    thread4.join()

    thread5.join()


if __name__ == "__main__":
    main()