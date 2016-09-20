'''
Created on 7 Sep 2016

@author: br54
'''
import unittest
import os

from icat import ICAT
from vicat import VICAT, VicatException


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
        self.fid = self.session.write(entity)[0]
        
        investigationType = {}
        investigationType["facility"] = {"id":self.fid}
        investigationType["name"] = "E"
        entity = {"InvestigationType" : investigationType}
        itid = self.session.write(entity)[0]
    
        entities = []
        for name in ["Inv 1"]:
            investigation = {}
            investigation["facility"] = {"id":self.fid}
            investigation["type"] = {"id":itid}
            investigation["name"] = name
            investigation["title"] = "The " + name
            investigation["visitId"] = "One"
            entities.append({"Investigation": investigation})
        self.session.write(entities)
        
        datasetType = {"name" :"DS Type", "facility" : {"id":self.fid}}
        entity = {"DatasetType" : datasetType}
        self.session.write(entity)
        
        # Add a dataset from which to create a new version
        invid = self.session.search("SELECT i.id FROM Investigation i WHERE i.facility.name = 'LSF' AND i.name = 'Inv 1'")[0]
        dstid = self.session.search("SELECT d.id FROM DatasetType d")[0]
        dataset = {"name" : "ds1", "investigation" : { "id" : invid}, "type": {"id":dstid}}
        dataset["datafiles"] = [{"name" : "df1", "location" : "loc1"}, {"name":"df2", "location" : "loc2"}]
        entity = {"Dataset" : dataset}
        self.datasetId = self.session.write(entity)[0]
        

    def tearDown(self):
        # We could delete the Facility we created; but it's useful to be able to inspect it after the last test.
        pass

    def test01CreateVersion(self):
        self.vicat = VICAT(self.session)
        newdsid = self.vicat.createVersion(self.datasetId,"ds1_v2")
        # The new dataset should be new
        self.assertNotEqual(self.datasetId,newdsid)
        # The new dataset should have the supersedes parameter set
        self.assertEqual(self.datasetId,self.vicat.supersedes(newdsid))
        # The old dataset should have the superseded parameter set
        self.assertTrue(self.vicat.isSuperseded(self.datasetId))
        # ... and the new one should not
        self.assertFalse(self.vicat.isSuperseded(newdsid))
        # The old and new datasets should have the same number of datafiles
        oldfiles = self.session.search("SELECT df.id, df.name, df.location FROM Datafile df WHERE df.dataset.id = " + str(self.datasetId))
        newfiles = self.session.search("SELECT df.id, df.name, df.location FROM Datafile df WHERE df.dataset.id = " + str(newdsid))
        self.assertEqual(len(oldfiles),len(newfiles))
        # Each datafile in the old dataset should have a corresponding new datafile in the new dataset
        for oldfile in oldfiles:
            found = False
            for newfile in newfiles:
                # ids should all be different
                self.assertNotEquals(oldfile[0],newfile[0])
                if oldfile[1] == newfile[1]:
                    # Locations should match
                    self.assertEqual(oldfile[2],newfile[2])
                    found = True
            self.assertTrue(found)

    def test02Branching(self):
        self.vicat = VICAT(self.session,self.fid,True)
        newdsid = self.vicat.createVersion(self.datasetId,"ds1_v2.1")
        # We should be able to create a second version of the same dataset
        newdsid2 = self.vicat.createVersion(self.datasetId,"ds1_v2.2")
        self.assertNotEqual(newdsid,newdsid2)
        # This is a more subtle test: newdsid2 should NOT inherit datasetId's 'superseded' parameter
        self.assertFalse(self.vicat.isSuperseded(newdsid2))
    
    def test03NoBranching(self):
        self.vicat = VICAT(self.session,self.fid,False)
        newdsid = self.vicat.createVersion(self.datasetId,"ds1_v2.1")
        # We should NOT be able to create a second version of the same dataset
        with self.assertRaises(VicatException) as cm:
            newdsid2 = self.vicat.createVersion(self.datasetId,"ds1_v2.2")
        self.assertEqual(VicatException.BRANCHING_NOT_PERMITTED, cm.exception.getType())
    
    def test04SupersededNone(self):
        self.vicat = VICAT(self.session,self.fid,False)
        self.assertIsNone(self.vicat.superseded(self.datasetId))
    
    def test05SupersededOK(self):
        self.vicat = VICAT(self.session,self.fid,False)
        newdsid = self.vicat.createVersion(self.datasetId,"ds1_v2.1")
        self.assertEqual(newdsid,self.vicat.superseded(self.datasetId))
    
    def test06SupersededNotOK(self):
        self.vicat = VICAT(self.session,self.fid,True)
        newdsid = self.vicat.createVersion(self.datasetId,"ds1_v2.1")
        with self.assertRaises(VicatException) as cm:
            dsid2 = self.vicat.superseded(self.datasetId)
        self.assertEqual(VicatException.BRANCHING_PERMITTED, cm.exception.getType())

    def test07SupersededNotOK(self):
        self.vicat = VICAT(self.session,self.fid,True)
        newdsid = self.vicat.createVersion(self.datasetId,"ds1_v2.1")
        # Naughty: create a new VICAT instance on this facility that assumes branching is not permitted
        self.vicat = VICAT(self.session,self.fid,False)
        with self.assertRaises(VicatException) as cm:
            dsid2 = self.vicat.superseded(self.datasetId)
        self.assertEqual(VicatException.BRANCHING_PERMITTED, cm.exception.getType())
    
    def test08History(self):
        self.vicat = VICAT(self.session,self.fid,False)
        self.assertEqual([],self.vicat.ancestors(self.datasetId))
        self.assertEqual([],self.vicat.descendants(self.datasetId))
        newdsid1 = self.vicat.createVersion(self.datasetId,"ds1_v2")
        newdsid2 = self.vicat.createVersion(newdsid1,"ds1_v3")
        self.assertEqual([self.datasetId,newdsid1],self.vicat.ancestors(newdsid2))
        self.assertEqual([newdsid1,newdsid2], self.vicat.descendants(self.datasetId))
        self.assertEqual([self.datasetId],self.vicat.ancestors(newdsid1))
        self.assertEqual([newdsid2], self.vicat.descendants(newdsid1))
    
    def test09SupersededTrail(self):
        self.vicat = VICAT(self.session,self.fid,False)
        newdsid1 = self.vicat.createVersion(self.datasetId,"ds1_v2")
        newdsid2 = self.vicat.createVersion(newdsid1,"ds1_v3")
        self.assertTrue(self.vicat.isSuperseded(self.datasetId))
        self.assertTrue(self.vicat.isSuperseded(newdsid1))
        self.assertFalse(self.vicat.isSuperseded(newdsid2))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testCreateVersion']
    unittest.main()