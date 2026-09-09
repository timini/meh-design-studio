"""Create a new private catalogue from the original, unqualified demo records."""
import argparse
import json
from pathlib import Path
from meh_studio.catalogue import Catalogue
from meh_studio.domain import DriverRevision


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path)
    args=parser.parse_args()
    fixture=Path(__file__).resolve().parents[2]/'examples/synthetic-search-drivers.json'
    drivers=[DriverRevision.model_validate(d) for d in json.loads(fixture.read_text())]
    if any(d.qualification is not None or d.provenance.kind!='synthetic' for d in drivers):
        raise ValueError('demo catalogue requires unqualified synthetic records')
    with Catalogue.create(args.database) as catalogue:
        for driver in drivers: catalogue.add(driver)
    print(json.dumps({'created':str(args.database),'driver_records':len(drivers),'qualified':False}))


if __name__=='__main__':main()
