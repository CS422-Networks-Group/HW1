import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import requests
import socket
import dns.resolver

def process_csv(csv_file: str) -> pd.DataFrame:

    #read the csv
    df = pd.read_csv(csv_file)

    #initialize two new columns
    df["Latitude"] = None
    df["Longitude"] = None
    
    #read each row in csv and obtain the latitude and longitude
    for index, row in df.iterrows():
        ip_addr = row["IP/HOST"]
        result = dns.resolver.resolve(ip_addr, 'A')
        response = requests.get(f"http://ipwho.is/{result}")
        print(response.json())

        


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
    return True



if __name__ == "__main__":
    main()