import pandas as pd
from pandas import Series, to_datetime, Timedelta
from timeUtils import clock, elapsed, getTimeSuffix, getDateTime, addDays, printDateTime, getFirstLastDay
from pandasUtils import castDateTime, castInt64, cutDataFrameByDate, convertToDate, isSeries, isDataFrame, getColData
from geoUtils import getDist
from collections import Counter



#############################################################################################################################
# Overnight Stays
#############################################################################################################################
class homeFinder():
    def __init__(self, debug=False):
        self.debug    = debug
        self.trips    = None
        self.clusters = None
        
        self.overnightStays = None
        self.dwellTimes     = None
        self.dailyVisits    = None
        self.lastVisits     = None
        self.clusterInfo    = {}
        
        
        self.startTimeName  = "Start"
        self.startDateName  = "StartDate"
        self.startLabelName = "StartLabel"
        self.endTimeName    = "End"
        self.endDateName    = "EndDate"
        self.endLabelName   = "EndLabel"
        
        

    def getHomeRatio(self):
        return self.homeRatio
    
    def getHomeList(self):
        return self.homeList
    
    def getHomeCluster(self):
        return self.homeCl
    
    def getClusterInfo(self, cl):
        return self.clusterInfo.get(cl)
        
        
    def setTrips(self, trips, startTimeName=None, startLabel=None, endTimeName=None, endLabel=None):
        if not isDataFrame(trips):
            raise ValueError("Trips must in a data frame")
            
        if startTimeName is not None:
            self.startTimeName  = startTimeName
        if startLabel is not None:
            self.startLabelName = startLabel
        if endTimeName is not None:
            self.startTimeName  = endTimeName
        if endLabel is not None:
            self.endLabelName   = endLabel

        ## Check for labels
        if self.startLabelName not in trips.columns:
            raise ValueError("Need a cluster label for the starting location called `{0}`: {1}".format(self.startLabelName, trips.columns))
        if self.endLabelName not in trips.columns:
            raise ValueError("Need a cluster label for the ending location called `{0}`: {1}".format(self.endLabelName, trips.columns))
            
        ## Check for times
        if self.startTimeName not in trips.columns:
            raise ValueError("Need a start time in the data frame called `{0}`: {1}".format(self.startTimeName, trips.columns))
        if self.endTimeName not in trips.columns:
            raise ValueError("Need an end time in the data frame called `{0}`: {1}".format(self.endTimeName, trips.columns))
            
        trips = trips.sort_values(by=self.startTimeName, ascending=True, inplace=False)
        trips[self.startDateName]    = convertToDate(castDateTime(trips[self.startTimeName]))
        trips[self.endDateName]      = convertToDate(castDateTime(trips[self.endTimeName]))
        
        self.clusters = set(set(trips[self.startLabelName]) | set(trips[self.endLabelName]))
        self.trips = trips
        
        #for tripno, trip in self.trips.iterrows():
        #    self.showTrip(tripno, trip)
        
        
    #############################################################################################################################
    # Show Trip Info
    #############################################################################################################################
    def showTrip(self, tripno, trip):
        startLabel  = trip[self.startLabelName]
        startDate = trip[self.startDateName]
        startTime = trip[self.startTimeName]
        endLabel    = trip[self.endLabelName]
        endDate   = trip[self.endDateName]
        endTime   = trip[self.endTimeName]
        duration  = ((endTime-startTime).seconds)/3600.0
        print("Trip: {0: <6}: {1: <5} --> {2: <5}\t{3: <11}, {4: <11}, {5} hours".format(tripno, startLabel, endLabel, str(startDate), str(endDate), round(duration,1)))

        
        
    #############################################################################################################################
    # Test if start is equal to previous end
    #############################################################################################################################
    def checkStartingLocation(self, startLabel, prevLabel, debug=False):
        return startLabel == prevLabel
    
    

    #############################################################################################################################
    # Last Visit
    #############################################################################################################################
    def getLastVisits(self, debug=False):        
        lastVisit = {}
        for tripno, trip in self.trips.iterrows():
            startLabel = trip[self.startLabelName]
            startDate  = trip[self.startDateName]
            startTime  = trip[self.startTimeName]
            endLabel   = trip[self.endLabelName]
            endDate    = trip[self.endDateName]
            endTime    = trip[self.endTimeName]
            
            if lastVisit.get(endLabel) is None:
                lastVisit[endLabel] = endDate
            else:
                lastVisit[endLabel] = max(endDate, lastVisit[endLabel])
            
            if lastVisit.get(startLabel) is None:
                lastVisit[startLabel] = startDate
            else:
                lastVisit[startLabel] = max(startDate, lastVisit[startLabel])

        self.lastVisits = Series(lastVisit)
    
    

    #############################################################################################################################
    # Dwell Time
    #############################################################################################################################
    def getOvernightStays(self, debug=False):        
        overnightStays = Counter()
        verydebug = False

        prevEndLabel  = None
        prevEndDate = None
        for tripno, trip in self.trips.iterrows():
            startLabel = trip[self.startLabelName]
            startDate  = trip[self.startDateName]
            startTime  = trip[self.startTimeName]
            endLabel   = trip[self.endLabelName]
            endDate    = trip[self.endDateName]
            endTime    = trip[self.endTimeName]
            if not all([startLabel,endLabel]):
                prevEndLabel  = None
                prevEndDate = None
                continue
            overnightStays[startLabel] += 0
            overnightStays[endLabel]   += 0

            if verydebug:
                self.showTrip(tripno, trip)

            if not self.checkStartingLocation(startLabel, prevEndLabel, debug):
                prevEndLabel  = endLabel
                prevEndDate = endDate
                if verydebug:
                    print("  Last Geo {0} and Start Geo {1} are too far apart or one is not recognized".format(startLabel, prevEndLabel))
                continue

            dTime = startDate - prevEndDate
            days  = dTime.days
            if days >= 1:
                overnightStays[startLabel] += 1
                if debug:
                    print("  Overnight Stay at {0: <5} {1: <4} from {2: <11} to {3: <11}".format(startLabel, "("+str(overnightStays[startLabel])+")", str(prevEndDate), str(startDate)))

            prevEndLabel  = endLabel
            prevEndDate = endDate

        self.overnightStays = Series(overnightStays)
        


    #############################################################################################################################
    # Dwell Time
    #############################################################################################################################
    def getDwellTimes(self, debug=False):
        dwellTimes = {}
        verydebug  = False

        prevEndLabel  = None
        prevEndTime = None
        for tripno, trip in self.trips.iterrows():
            startLabel  = trip[self.startLabelName]
            startDate = trip[self.startDateName]
            startTime = trip[self.startTimeName]
            endLabel    = trip[self.endLabelName]
            endDate   = trip[self.endDateName]
            endTime   = trip[self.endTimeName]
            if not all([startLabel,endLabel]):
                prevEndLabel  = None
                prevEndTime = None
                continue

            if verydebug:
                self.showTrip(tripno, trip)

            if not self.checkStartingLocation(startLabel, prevEndLabel, debug):
                prevEndLabel  = endLabel
                prevEndTime = endTime
                if verydebug:
                    print("  Last Geo {0} and Start Geo {1} are too far apart or one is not recognized".format(startLabel, prevEndLabel))
                continue

            dTime = startTime - prevEndTime
            hours = dTime.seconds/3600
            if hours < 24:
                if dwellTimes.get(startLabel) is None:
                    dwellTimes[startLabel] = []
                dwellTimes[startLabel].append(hours)

                if debug:
                    print("  Dwell Time at {0: <5} is {1} hours.".format(startLabel, round(hours,1)))

            prevEndLabel  = endLabel
            prevEndTime = endTime
            
        retval = {}
        for geo,dtime in dwellTimes.items():
            retval[geo] = Series(dtime).mean()
                
        self.dwellTimes = Series(retval)
        
                

    #############################################################################################################################
    # Get Daily Visits
    #############################################################################################################################
    def getDailyVisits(self, debug=False):
        dvData = {}
        for tripno, trip in self.trips.iterrows():
            startLabel  = trip[self.startLabelName]
            startDate = trip[self.startDateName]
            startTime = trip[self.startTimeName]
            endLabel    = trip[self.endLabelName]
            endDate   = trip[self.endDateName]
            endTime   = trip[self.endTimeName]
            if not all([startLabel,endLabel]):
                prevEndLabel  = None
                prevEndTime = None
                continue
            
            if dvData.get(startLabel) is None:
                dvData[startLabel] = set()
            if dvData.get(endLabel) is None:
                dvData[endLabel] = set()


            dvData[startLabel].add(startDate)
            dvData[endLabel].add(endDate)

        dvData = {k: len(v) for k,v in dvData.items()}
        self.dailyVisits = Series(dvData)


    #############################################################################################################################
    # Guess Home
    #############################################################################################################################
    def getHome(self, debug=False, verydebug=False):
        if debug:
            print("Deriving Home From Daily Visits, Overnight Stays, Dwell Times, and Common Location")

        #if not all([self.dailyVisits, self.overnightStays, self.dwellTimes]):
        #    raise ValueError("Must run daily visits, overnight stays, and dwell times before finding home")

        if debug:
            print("There are {0} possible home clusters".format(len(self.clusters)))

            
        dwellTimesDict     = self.dwellTimes.to_dict()
        overnightStaysDict = self.overnightStays.to_dict()
        dailyVisitsDict    = self.dailyVisits.to_dict()
        lastVisitsDict     = self.lastVisits.to_dict()
        for cl in self.clusters:
            self.clusterInfo[cl] = {"DwellTime": dwellTimesDict.get(cl),
                                    "OvernightStays": overnightStaysDict.get(cl),
                                    "LastVisit": lastVisitsDict.get(cl),
                                    "DailyVisits": dailyVisitsDict.get(cl)}
            

        #### Require last visit within 30 days of most recent trip
        lastTripDate = self.lastVisits.max()
        candidateLastVisit = self.lastVisits[self.lastVisits - lastTripDate > Timedelta('-30 days')].index
        if debug:
            print("There are {0} possible home clusters with a visit within last 30 days".format(len(candidateLastVisit)))
            if verydebug:
                print("  CLs: {0}".format(list(candidateLastVisit)))
            

        #### Require at least two hours of dwell time
        candidateDwellTimes = self.dwellTimes[(self.dwellTimes >= 2)].index
        if debug:
            print("There are {0} possible home clusters with at least two hours of dwell time".format(len(candidateDwellTimes)))
            if verydebug:
                print("  CLs: {0}".format(list(candidateDwellTimes)))


        #### Require at least ten daily visits
        candidateDailyVisits = self.dailyVisits[(self.dailyVisits >= 10)].index
        if debug:
            print("There are {0} possible home clusters with at least ten daily visits".format(len(candidateDailyVisits)))
            if verydebug:
                print("  CLs: {0}".format(list(candidateDailyVisits)))


        ### Require at least one overnight stay
        candidateOvernightStays = self.overnightStays[(self.overnightStays >= 1)].index
        if debug:
            print("There are {0} possible home clusters with at least one overnight stay".format(len(candidateOvernightStays)))
            if verydebug:
                print("  CLs: {0}".format(list(candidateOvernightStays)))



        candidates = set(candidateLastVisit) & set(candidateDwellTimes) & set(candidateDailyVisits) & set(candidateOvernightStays)
        if debug:
            print("There are {0} possible home clusters with all requirements".format(len(candidates)))
            if verydebug:
                print("  CLs: {0}".format(list(candidates)))


        finallist = self.overnightStays[self.overnightStays.index.isin(list(candidates))]
        finallist.sort_values(ascending=False, inplace=True)
        if verydebug:
            print("  Ranked CLs: {0}".format(list(finallist.index)))

        
        possibleHomes  = finallist.count()
        try:
            homeCl     = finallist.index[0]
        except:
            homeCl     = None

        try:
            nextCl     = finallist.index[1]
            homeRatio  = round(finallist[homeCl]/finallist[nextCl],1)
        except:
            homeRatio  = None
            
            
        self.homeCl      = homeCl
        self.homeRatio   = homeRatio
        self.homeList    = finallist
        
        if debug:
            print("Home cluster is {0} with {1} significance".format(homeCl, homeRatio))

            
        return homeCl