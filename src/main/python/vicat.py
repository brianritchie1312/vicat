'''
Created on 7 Sep 2016

@author: br54
'''
from icat import ICAT

class VICAT(object):
    '''
    An ICAT client that supports versioning of datasets.
    '''

    # Names of the versioning ParameterTypes
    SUPERSEDED = "superseded"
    SUPERSEDES = "supersedes"

    def __init__(self, session, facilityId = None):
        '''
        Constructor; takes an ICAT session and an optional Facility ID.
        If the facilityId is not specified, look for a Facility called LSF
        (which must exist).
        Versioning uses two dataset parameters, "superseded" and "supersedes";
        these will be created on the Facility if they do not already exist.
        '''
        self.session = session
        if facilityId:
            self.fid = facilityId
        else:
            # Legacy: look for the LSF facility if no id is specified
            fids = self.session.search("SELECT f.id FROM Facility f WHERE f.name = 'LSF'")
            if len(fids) == 1:
                self.fid = fids[0]
            else:
                raise Exception("No Facility specified and can't find a Facility called LSF")
        self._setupDatasetParameters()

    def _setupDatasetParameters(self):
        pts = self.session.search("SELECT pt.id FROM ParameterType pt WHERE pt.facility.id = " + str(self.fid) + " AND pt.name = '" + self.SUPERSEDED + "'")
        if pts and len(pts) > 0:
            self.supersededPT = pts[0]
        else:
            sdParamType = {"name" : self.SUPERSEDED,
                "facility" : {"id" : self.fid},
                "valueType" : "STRING",
                "description" : "indicates there are newer versions of this dataset",
                "applicableToDataset" : True,
                "units" : "N/A"}
            entity = {"ParameterType" : sdParamType }
            self.supersededPT = self.session.write(entity)[0]
        
        pts = self.session.search("SELECT pt.id FROM ParameterType pt WHERE pt.facility.id = " + str(self.fid) + " AND pt.name = '" + self.SUPERSEDES + "'")
        if pts and len(pts) > 0:
            self.supersedesPT = pts[0]
        else:
            ssParamType = {"name" : self.SUPERSEDES,
                "facility" : {"id" : self.fid},
                "valueType" : "NUMERIC",
                "description" : "indicates this dataset is a newer version of the given datasetId",
                "applicableToDataset" : True,
                "units" : "N/A"}
            entity = {"ParameterType" : ssParamType }
            self.supersedesPT = self.session.write(entity)[0]

    def createVersion(self, datasetId, newName):
        newdsid = self.session.cloneEntity("Dataset", datasetId, {"name": newName })
        # Add 'supersedes' dataset parameter
        supersedesParam = {"dataset" : {"id" : newdsid}, "type" : {"id" : self.supersedesPT}, "numericValue" : datasetId}
        entity = {"DatasetParameter" : supersedesParam}
        self.session.write(entity)

        # Add 'superseded' parameter to original dataset,
        # if it's not there already
        sdParams = self.session.search("SELECT dp.id FROM DatasetParameter dp WHERE dp.dataset.id="+str(datasetId)+" AND dp.type.id="+str(self.supersededPT))
        if len(sdParams) == 0:
            supersededParam = {"dataset" : {"id" : datasetId}, "type" : {"id" : self.supersededPT}, "stringValue" : "true"}
            entity = {"DatasetParameter" : supersededParam}
            self.session.write(entity)
        
        return newdsid

    def isSuperseded(self, datasetId):
        '''
        True if one or more new versions have been created from this Dataset
        '''
        sdParams = self.session.search("SELECT dp.id FROM DatasetParameter dp WHERE dp.dataset.id="+str(datasetId)+" AND dp.type.id="+str(self.supersededPT))
        return len(sdParams) > 0
    
    def supersedes(self, datasetId):
        '''
        If this dataset is a new version, return the datasetId of the dataset it (immediately) supersedes.
        If it is not a version, return None
        '''
        ssParams = self.session.search("SELECT dp.id, dp.numericValue FROM DatasetParameter dp WHERE dp.dataset.id="+str(datasetId)+" AND dp.type.id="+str(self.supersedesPT))
        if len(ssParams) == 0:
            return None
        else:
            return ssParams[0][1]

