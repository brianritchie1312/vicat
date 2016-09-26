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
    # Attempt to use a non-branching operation when branching is in effect
    BRANCHING_PERMITTED = "BRANCHING_PERMITTED"
    
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
    SUPERSEDED = "vicat:superseded"
    SUPERSEDES = "vicat:supersedes"
    COMMENT = "vicat:comment"

    def __init__(self, session, facilityId = None, branching = False):
        '''
        Constructor; takes an ICAT session, an optional Facility ID and an optional branching flag.
        If the facilityId is not specified, look for a Facility called LSF
        (which must exist).
        If the branching flag is set to False (the default), then each dataset can have
        no more than one direct version, and version histories will be linear;
        an attempt to create a second version from a dataset will raise an exception.
        If the branching flag is set to True, then multiple direct versions of the same
        dataset will be allowed, and version histories need no longer be linear. In this
        case, a dataset may not have a single "latest" version, and an attempt to request
        this will raise an exception.
        WARNING: the branching property is persistent for the chosen Facility, but it is not
        (directly) recorded. (A pragmatic test would be to look for any datasets where the
        "vicat:superseded" parameter (see below) has been set to 0; this would indicate that branching
        has been True.)
        The consequences of creating a VICAT instance with branching=False on 
        a Facility where branching has been True previously are unpredictable.
        Versioning uses three dataset parameters, "vicat:superseded", "vicat:supersedes" and "vicat:comment";
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
        
        pts = self.session.search("SELECT pt.id FROM ParameterType pt WHERE pt.facility.id = " + str(self.fid) + " AND pt.name = '" + self.COMMENT + "'")
        if pts and len(pts) > 0:
            self.commentPT = pts[0]
        else:
            commentParamType = {"name" : self.COMMENT,
                "facility" : {"id" : self.fid},
                "valueType" : "STRING",
                "description" : "documents reason for creation of this version of the given datasetId",
                "applicableToDataset" : True,
                "units" : "N/A"}
            entity = {"ParameterType" : commentParamType }
            self.commentPT = self.session.write(entity)[0]

    def _findParam(self, datasetId, paramTypeId, valueTypeField=None):
        """
        Find and return a list of any ids of (Dataset)Parameters of the given type for the given dataset.
        If valueTypeField is not None, add it to the selectors; in this case, each list element will
        be a list containing the id and the value of the named field.
        """
        selectors = "dp.id"
        if valueTypeField is not None:
            selectors += ", dp." + valueTypeField
        return self.session.search("SELECT " + selectors + " FROM DatasetParameter dp WHERE dp.dataset.id="+str(datasetId)+" AND dp.type.id="+str(paramTypeId))
    
    def _addOrUpdateParameter(self, datasetId, paramTypeId, paramValue=None, valueTypeField="numericValue"):
        """
        If the given dataset already has an instance of the paramType, delete it first.
        Create an instance of paramType for the given dataset with the given value.
        If paramValue is None, then any existing parameter will be deleted, but no
        new value will be created.
        The valueTypeField must match that expected for the given paramType.
        """
        params = self._findParam(datasetId, paramTypeId)
        if len(params) != 0:
            paramId = params[0]
            entity = {"DatasetParameter" : {"id" : paramId}}
            self.session.delete(entity)
        if paramValue is not None:
            newParam = {"dataset" : {"id" : datasetId}, "type" : {"id" : paramTypeId}, valueTypeField : paramValue}
            entity = {"DatasetParameter" : newParam}
            self.session.write(entity)

    def createVersion(self, datasetId, newName, versionComment=None):
        """
        Create a new version of the given dataset, using the new name.
        Returns the id of the new dataset.
        versionComment can be used to document the reason for the new version.
        """
        # Check whether the dataset already has a newer version
        sdParams = self._findParam(datasetId, self.supersededPT)
        if len(sdParams) != 0 and not self.branching:
            raise VicatException(VicatException.BRANCHING_NOT_PERMITTED,"Attempt to create second version of dataset " + str(datasetId) + " when branching is not allowed.")
        
        newdsid = self.session.cloneEntity("Dataset", datasetId, {"name": newName })
        
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
        
        # Subtle point: if branching is allowed, after the first version there will be a 'superseded' parameter in this clone,
        # which must be removed
        self._addOrUpdateParameter(newdsid, self.supersededPT)
        
        # Add 'supersedes' dataset parameter, or replace it (if the original was already a version dataset)
        self._addOrUpdateParameter(newdsid, self.supersedesPT, datasetId)
        
        # Add the version comment (or remove any comment left over from the original clone
        self._addOrUpdateParameter(newdsid, self.commentPT, versionComment, "stringValue")

        return newdsid

    def isSuperseded(self, datasetId):
        '''
        True if one or more new versions have been created from this Dataset
        '''
        sdParams = self._findParam(datasetId, self.supersededPT)
        return len(sdParams) > 0
    
    def superseded(self, datasetId):
        """
        Return the dataset id of the dataset, if any, that is the next newest version of the given dataset.
        If there is no newer version, return None.
        If branching is permitted, this raises an exception.
        """
        if self.branching:
            raise VicatException(VicatException.BRANCHING_PERMITTED,"Attempt to obtain single descendant from dataset " + str(datasetId) + " when branching is permitted")

        sdParams = self._findParam(datasetId, self.supersededPT, "numericValue")
        if len(sdParams) == 0:
            return None
        else:
            sdVal = sdParams[0][1]
            # Secondary guard: this instance may not believe branching is permitted,
            # but it may have been allowed in the past - note different error message!
            if sdVal == 0:
                raise VicatException(VicatException.BRANCHING_PERMITTED,"Attempt to obtain single descendant from dataset " + str(datasetId) + " that was superseded when branching was permitted")
            else:
                return sdVal
    
    def supersedes(self, datasetId):
        '''
        If this dataset is a new version, return the datasetId of the dataset it (immediately) supersedes.
        If it is not a version, return None
        '''
        ssParams = self._findParam(datasetId, self.supersedesPT, "numericValue")
        if len(ssParams) == 0:
            return None
        else:
            return ssParams[0][1]

    def ancestors(self, datasetId):
        """
        Returns a list of ancestors (previous versions) of the given datasetId.
        """
        parent = self.supersedes(datasetId)
        if parent is not None:
            return self.ancestors(parent) + [parent]
        else:
            return []
    
    def descendants(self, datasetId):
        """
        Returns a list of descendants (newer versions) of the given datasetId.
        This operation is not permitted when branching is in effect.
        """
        if self.branching:
            raise VicatException(VicatException.BRANCHING_PERMITTED,"Attempt to obtain descendants from dataset " + str(datasetId) + " when branching is permitted")
        child = self.superseded(datasetId)
        if child is not None:
            return [child] + self.descendants(child)
        else:
            return []

    def versionComment(self,datasetId):
        """
        Return the version comment for the given datasetId, if it has one
        """
        sdParams = self._findParam(datasetId, self.commentPT, "stringValue")
        if len(sdParams) == 0:
            return None
        else:
            return sdParams[0][1]
        

