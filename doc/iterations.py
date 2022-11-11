from itertools import combinations, product
from automatic_university_scheduling.scheduling import read_json_data

activities = read_json_data("./activity_data/")
activity = activities["COMMUNICATION"]["activities"]["COM_TDA5"]
rooms = activity["rooms"]
teachers = activity["teachers"]
kind = []
items = []
for number, teacherpool in teachers:
    items.append(combinations(teacherpool, number))
    kind.append("teacher")
for number, roompool in rooms:
    items.append(combinations(roompool, number))
    kind.append("room")
combinations = [p for p in product(*items)]
for combination in combinations:
    print(kind, combination)
