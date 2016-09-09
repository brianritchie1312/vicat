'''
Created on 7 Sep 2016

@author: br54
'''
import unittest
import os

from icat import ICAT
from vicat import VICAT


class Test(unittest.TestCase):


    def setUp(self):
        self.icat = ICAT(os.environ["serverUrl"], os.environ["serverCert"])
        self.session = self.icat.login("simple", {"username":"br54", "password":"bubbleicatcar"})
        # wipe and reset ICAT
        for fid in self.session.search("SELECT f.id from Facility f"):
            f = {"Facility": {"id" : fid}}
            self.session.delete(f)
        facility = {}
        facility["name"] = "LSF"
        entity = {"Facility":facility}
        fid = self.session.write(entity)[0]
        
        investigationType = {}
        investigationType["facility"] = {"id":fid}
        investigationType["name"] = "E"
        entity = {"InvestigationType" : investigationType}
        itid = self.session.write(entity)[0]
    
        entities = []
        for name in ["Inv 1"]:
            investigation = {}
            investigation["facility"] = {"id":fid}
            investigation["type"] = {"id":itid}
            investigation["name"] = name
            investigation["title"] = "The " + name
            investigation["visitId"] = "One"
            entities.append({"Investigation": investigation})
        self.session.write(entities)
        
        datasetType = {"name" :"DS Type", "facility" : {"id":fid}}
        entity = {"DatasetType" : datasetType}
        self.session.write(entity)
        
        # Add a dataset from which to create a new version
        invid = self.session.search("SELECT i.id FROM Investigation i WHERE i.facility.name = 'LSF' AND i.name = 'Inv 1'")[0]
        dstid = self.session.search("SELECT d.id FROM DatasetType d")[0]
        dataset = {"name" : "ds1", "investigation" : { "id" : invid}, "type": {"id":dstid}}
        dataset["datafiles"] = [{"name" : "df1", "location" : "loc1"}, {"name":"df2", "location" : "loc2"}]
        entity = {"Dataset" : dataset}
        self.datasetId = self.session.write(entity)[0]
        
        # Create a VICAT instance
        self.vicat = VICAT(self.session)
        

    def tearDown(self):
        # We could delete the Facility we created; but it's useful to be able to inspect it after the last test.
        pass

    def testCreateVersion(self):
        newdsid = self.vicat.createVersion(self.datasetId,"ds1_v2")
        # The new dataset should be new
        self.assertNotEqual(self.datasetId,newdsid)
        # The new dataset should have the supersedes parameter set
        self.assertEquals(self.datasetId,self.vicat.supersedes(newdsid))
        # The old dataset should have the superseded parameter set
        self.assertTrue(self.vicat.isSuperseded(self.datasetId))
        # The old and new datasets should have the same number of datafiles
        oldfiles = self.session.search("SELECT df.id, df.name, df.location FROM Datafile df WHERE df.dataset.id = " + str(self.datasetId))
        newfiles = self.session.search("SELECT df.id, df.name, df.location FROM Datafile df WHERE df.dataset.id = " + str(newdsid))
        self.assertEquals(len(oldfiles),len(newfiles))
        # Each datafile in the old dataset should have a corresponding new datafile in the new dataset
        for oldfile in oldfiles:
            found = False
            for newfile in newfiles:
                # ids should all be different
                self.assertNotEquals(oldfile[0],newfile[0])
                if oldfile[1] == newfile[1]:
                    # Locations should match
                    self.assertEquals(oldfile[2],newfile[2])
                    found = True
            self.assertTrue(found)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testCreateVersion']
    unittest.main()