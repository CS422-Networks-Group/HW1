import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import requests
import socket
import ipaddress
import subprocess


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

    #initialize two new columns
    df["LATITUDE"] = None
    df["LONGITUDE"] = None
    
    #read each row in csv and obtain the latitude and longitude
    for index, row in df.iterrows():
        ip_or_host = row["IP/HOST"]
        valid_ip = True
        if not is_ip_address(ip_or_host):
            
            #TODO: figure this out, there's some bad/invalid ip addresses on here. 
            # also need to add our computer's ip addresses when the script is ran
            try:
                ip_or_host = socket.gethostbyname(ip_or_host)
            except socket.gaierror:
                valid_ip = False
        if valid_ip:

            #TODO: this may have to change. i'm getting rate limiter errors. maybe we can figure out an offline solution?
            response = requests.get(f"http://ipwho.is/{ip_or_host}")
            data = response.json()
    
            #setting the df values
            df.loc[index, "IP/HOST"] = ip_or_host

            #tODO
            df.loc[index, "LONGITUDE"] = data.get["longitude"]
            df.loc[index, "LATITUDE"] = response.get["latitude"]
        
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
        res = subprocess.run(["ping", "-c", "1", row["IP/HOST"]], capture_output=True, text=True)
        print(res)
    return True

if __name__ == "__main__":
    main()