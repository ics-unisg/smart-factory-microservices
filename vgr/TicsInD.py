tpRI = 63.3  # tics per revolution Input gear
r = 2  # ratio
tpRO = tpRI / r  # tics per revolution Output gear

diPr = 4.75  # distance per revolution (in mm)
dePr = 7.347  # degree per revolution

tPdi = tpRO / diPr  # tics per distance
tPde = tpRO / dePr  # tics per degree


# to convert tics to degrees the number of tics is divided by tics per degree!
def t_in_deg(t):  # ticks in degree
    return float("{:.2f}".format(t / tPde))


# to convert tics to mm the number of tics is divided by tics per mm!
def t_in_di(t):  # ticks in distance(mm)
    return float("{:.2f}".format(t / tPdi))


# to convert the number of degree to tics, multiply the number of degree by tics per degree!
def deg_in_t(deg):  # degree in ticks
    return "{:.2f}".format(deg * tPde)


# to convert the distance(mm) to tics, multiply the length (mm) by ticks per distance(mm)!
def di_in_t(di):  # distance(mm) in ticks
    return "{:.2f}".format(di * tPdi)
