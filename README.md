# vicat
A Python ICAT client that supports versioning of datasets

## Introduction
vicat uses the ICAT cloning mechanism to enable users to create and trace new versions of datasets.
The main anticipated use case is where a user wishes to create a new version of an original ingested dataset
whose contents (datafiles and metadata) may be modified while leaving the original dataset unchanged.
The class provides methods to create new versions, to determine whether a dataset has been superseded by
a newer version, and to retrieve the ancestors and (if possible) descendants of a dataset in the version
history.

The implementation uses DatasetParameters to record the version history; as these have to be defined for
a particular Facility, vicat must be initialised with a particular Facility.
(For pragmatic reasons, the default Facility is LSF.)

### Branching vs. non-branching
Versioning may be *branching* or *non-branching*. 
The simpler case is when branching is not allowed. Each dataset may have only one direct new version
(attempts to create a second will fail). For any dataset, the descendants will be linear (not tree-like),
and each dataset will have a unique latest version.
When branching is allowed, vicat allows users
to create multiple direct versions from the same dataset, so permitting a tree of descendants. In this case,
it is not guaranteed that each dataset will have a unique latest version. For reasons of simplicity, the
`descendants` method is not allowed.

The decision of whether to permit or forbid branching is determined in the vicat constructor. However, it is
*not* recorded in ICAT itself (though it *may* be possible to determine whether or not branching has been
permitted on a Facility previously). It is possible for a user to create a client that permits (or forbids)
branching on a Facility where it has previously been forbidden (or permitted). This can lead to unpredictable
failures, and is **not recommended**. 

### Limitations
vicat itself does not provide methods for modifying the contents of a dataset, as this can be achieved 
using other clients on the new version of the dataset.

There are no built-in methods to obtain the latest version of a dataset, or the original version: instead, use the `descendants`
or `ancestors` methods and choose the appropriate end of the list. A similar approach applies to obtaining the latest
version of a datafile, or the latest metadata, for an arbitrary dataset.

Once a new version has been created, it is not possible to delete it.

### NOTE on the unit tests
The setup method for the unit tests is designed to clean out the ICAT instance specified in the OS environment variable
`serverUrl`, so this should **not** be pointed to an ICAT instance that contains anything of value. (That said, the test
suite also assumes specific authentication credentials that are "unlikely" to be valid.)

## Constructor

### `VICAT(session, facilityId = None, branching = False)`

Takes an ICAT session, an optional Facility ID and an optional branching flag.

If the facilityId is not specified, it looks for a Facility called LSF
(which must exist).

If the branching flag is set to False (the default), then each dataset can have
no more than one direct version, and version histories will be linear;
an attempt to create a second version from a dataset will raise an exception.

If the branching flag is set to True, then multiple direct versions of the same
dataset will be allowed, and version histories need no longer be linear. In this
case, a dataset may not have a single "latest" version, and an attempt to request
this will raise an exception.

**NOTE**: the branching property is persistent for the chosen Facility,
but it is not (directly) recorded. (A pragmatic test would be to look
for any datasets where the `vicat:superseded` parameter (see below)
has been set to 0; this would indicate that branching has been True.)
The consequences of creating a VICAT instance with branching=False on
a Facility where branching has been True previously are unpredictable.

Versioning uses three dataset parameters, `vicat:superseded`,
`vicat:supersedes` and `vicat:comment`; these will be created for the
Facility if they do not already exist.

## Methods

### `createVersion(datasetId, newName, versionComment = None)`

Creates a new version of the given dataset, using the new name. Returns the id of the new dataset.

The new dataset contains "clones" of the old dataset's datafiles;
each Datafile is a new entity, but shares the location of the original.

DatasetParameters are also cloned (except for parameters maintained by
the versioning system itself).

versionComment can be used to document the reason for the new version.

If branching is False, an attempt to create a new version from a dataset
that already has a version will throw an exception.

### `isSuperseded(datasetId)`

Returns True if there is a newer version of the given datasetId.


### `superseded(datasetId)`

Returns the dataset id of the dataset, if any, that is the next newest
version of the given dataset.

If there is no newer version, None is returned.

If branching is permitted, this raises an exception.
If branching is not permitted, but the given datasetId was superseded when
branching *was* permitted, this also raises an exception (with a subtly different message).


### `supersedes(datasetId)`

If this dataset is a new version, returns the datasetId of the dataset
it (immediately) supersedes.

If it is not a version, returns None


### `ancestors(datasetId)`

Returns a list of ancestors (previous versions) of the given datasetId.


### `descendants(datasetId)`

Returns a list of descendants (newer versions) of the given datasetId.

This operation is not permitted when branching is in effect.


### `versionComment(datasetId)`

Returns the version comment for the given datasetId, or None if it does not have one.

