'''
Created on 7 Sep 2016

@author: br54
'''
from icat import ICAT

class VicatException(Exception):
    """
    Thrown by the code to indicate problems.
    """
    
    # No Facility specified and default LSF Facility cannot be found
    NO_FACILITY = "NO_FACILITY"
    # Attempt to branch versions when branching is not permitted
    BRANCHING_NOT_PERMITTED = "BRANCHING_NOT_PERMITTED"
    
    def __init__(self, code, message, offset=-1):
        """
        Not expected to be called by most users
        """
        self.code = code
        self.message = message
        self.offset = offset
        
    def __str__(self):
        return self.code + ": " + self.message
    
    def getMessage(self):
        """
        Return a human readable message
        """
        return self.message
    
    def getType(self):
        """
        Return the type of the exception as a string
        """
        return self.code
    
    def getOffset(self):
        """
        Return the offset or -1 if not applicable
        """
        return self.offset

class VICAT(object):
    '''
    An ICAT client that supports versioning of datasets.
    '''

    # Names of the versioning ParameterTypes
    SUPERSEDED = "superseded"
    SUPERSEDES = "supersedes"

    def __init__(self, session, facilityId = None, branching = False):
        '''
        Constructor; takes an ICAT session, an optional Facility ID and an optional branching flag.
        If the facilityId is not specified, look for a Facility called LSF
        (which must exist).
        If the branching flag is set to False (the default), then each dataset can have
        no more than one direct version, and version histories will be linear.
        An attempt to create a second version from a dataset will raise an exception.
        If the branching flag is set to True, then multiple direct versions of the same
        dataset will be allowed, and version histories need no longer be linear. In this
        case, a dataset may not have a single "latest" version, and an attempt to request
        this will raise an exception.
        WARNING: the branching property is persistent for the chosen Facility. The consequences
        of creating a VICAT instance with branching=False on a Facility where branching
        has been True previously are unpredictable.
        Versioning uses two dataset parameters, "superseded" and "supersedes";
        these will be created on the Facility if they do not already exist.
        '''
        self.session = session
        self.branching = branching
        if facilityId:
            self.fid = facilityId
        else:
            # Legacy: look for the LSF facility if no id is specified
            fids = self.session.search("SELECT f.id FROM Facility f WHERE f.name = 'LSF'")
            if len(fids) == 1:
                self.fid = fids[0]
            else:
                raise VicatException(VicatException.NO_FACILITY,"No Facility specified and can't find a Facility called LSF")
        self._setupDatasetParameters()

    def _setupDatasetParameters(self):
        pts = self.session.search("SELECT pt.id FROM ParameterType pt WHERE pt.facility.id = " + str(self.fid) + " AND pt.name = '" + self.SUPERSEDED + "'")
        if pts and len(pts) > 0:
            self.supersededPT = pts[0]
        else:
            sdParamType = {"name" : self.SUPERSEDED,
                "facility" : {"id" : self.fid},
                "valueType" : "NUMERIC",
                "description" : "indicates there are newer versions of this dataset; if branching is disabled, will contain the id of the superseding dataset",
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
        # Check whether the dataset already has a newer version
        sdParams = self.session.search("SELECT dp.id FROM DatasetParameter dp WHERE dp.dataset.id="+str(datasetId)+" AND dp.type.id="+str(self.supersededPT))
        if len(sdParams) != 0 and not self.branching:
            raise VicatException(VicatException.BRANCHING_NOT_PERMITTED,"Attempt to create second version of dataset " + str(datasetId) + " when branching is not allowed.")
        
        newdsid = self.session.cloneEntity("Dataset", datasetId, {"name": newName })
        # Add 'supersedes' dataset parameter
        supersedesParam = {"dataset" : {"id" : newdsid}, "type" : {"id" : self.supersedesPT}, "numericValue" : datasetId}
        entity = {"DatasetParameter" : supersedesParam}
        self.session.write(entity)

        # Add 'superseded' parameter to original dataset,
        # if it's not there already
        if len(sdParams) == 0:
            if self.branching:
                supersededValue = 0
            else:
                supersededValue = newdsid
            supersededParam = {"dataset" : {"id" : datasetId}, "type" : {"id" : self.supersededPT}, "numericValue" : supersededValue}
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

