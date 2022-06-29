#!/usr/bin/env python3
"""
Run form project root dir.
Finds a missing definiton of a host/guest that is present in one of the episodes.

When the preson json file is not there but is referenced in an episode, this error
is thrown on build:
    
    ```
    Error: Error building site: failed to render pages: render of "page" failed: 
    execute of template failed: template: episode/single.html:51:25: executing "main" 
    at <partial "guests/small.html" (dict "context" . "guest" $guest)>: error calling 
    partial: "/build/themes/jb/layouts/partials/guests/small.html:3:30": execute of 
    template failed: template: partials/guests/small.html:3:30: executing 
    "partials/guests/small.html" at <.guest.username>: nil pointer evaluating interface 
    {}.username
    ```
"""

import os
import concurrent.futures
import json

# KEYS are the list variables located in the TOML section in the episode files which
# containe the people in the episode
PPL_KEYS = {"guests", "hosts"}  
SHOWS_DIR = "./content/show"
PERSONS_DIRS = {"./data/guests", "./data/hosts"}


def read_file(show, ep):
    with open(os.path.join(SHOWS_DIR, show, ep), "r") as f:
        line = f.readline()
        key = None
        if " = " in line:
            key, val = line.split(" = ")
        while line and key not in PPL_KEYS:
            line = f.readline()
            if " = " in line:
                key, val = line.split(" = ")
        
        if key and key in PPL_KEYS:
            # print(f"{show} {ep}: {val}")
            return json.loads(val)
    # print(f"{show} {ep}: -")
    return None


def main():
    ppl_by_dir = {}
    ppl_defined = set()
    for d in PERSONS_DIRS:
        ppl_in_dir = set()
        for p in os.listdir(path=d):
            ppl_in_dir.add(p[:-5]) # remove the last 5 chars ".json" 
        ppl_defined = ppl_defined.union(ppl_in_dir)
        ppl_by_dir.update({d: ppl_in_dir})

    futures = []
    for show in os.listdir(path=SHOWS_DIR):
        for ep in os.listdir(path=os.path.join(SHOWS_DIR, show)):
            if ep == "_index.json":
                continue
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures.append(executor.submit(read_file, show, ep))


    ppl_referenced = set()
    for future in concurrent.futures.as_completed(futures):
        ppl_in_one_file = future.result()
        ppl_referenced = ppl_referenced.union(ppl_in_one_file)

    diff = len(ppl_defined)-len(ppl_referenced)

    print(f"Defined people:    {len(ppl_defined):4}")
    print(f"Referenced people: {len(ppl_referenced):4}")
    print(f"Difference:        {diff:4}")

    print("\n==========================")
    print("Missing definition files:")
    print("==========================")
    missing_defs = (ppl_referenced - ppl_defined)
    for d in missing_defs:
        ptype = None
        for key, ppl_in_dir in ppl_by_dir.items():
            if d in ppl_in_dir:
                ptype = key
                break

        print(f"{d} ({ptype})")
    
    print("\n==========================")
    print("Not referenced people:")
    print("==========================\n")
    for d in (ppl_defined - ppl_referenced):
        print(d)

if __name__ ==  "__main__":
    main()