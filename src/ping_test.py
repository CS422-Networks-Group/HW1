import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import requests
import socket
import ipaddress
import subprocess
import IP2Location  
import os

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
    
    #running ping tests
    for _, row in df.iterrows():
        res = subprocess.run(["ping", "-c", "11", row["IP/HOST"]], capture_output=True, text=True)
        print(res)
    return True

if __name__ == "__main__":
    main()