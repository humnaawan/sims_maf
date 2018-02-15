"""Some basic physical quantity metrics.
"""
import lsst.sims.maf.metrics as metrics
import lsst.sims.maf.slicers as slicers
import lsst.sims.maf.stackers as stackers
import lsst.sims.maf.plots as plots
import lsst.sims.maf.metricBundles as mb
from .colMapDict import ColMapDict
from .common import standardSummary, extendedMetrics, filterList

__all__ = ['metadataBasics', 'allMetadata']


def metadataBasics(value, colmap=None, runName='opsim',
                   valueName=None, groupName=None, extraSql=None, extraMetadata=None,
                   nside=64, filterlist=('u', 'g', 'r', 'i', 'z', 'y')):
    """Calculate basic metrics on visit metadata 'value' (e.g. airmass, normalized airmass, seeing..).

    Calculates extended standard metrics (with unislicer) on the quantity (all visits and per filter),
    makes histogram of the value (all visits and per filter),

    TODO: handle stackers which need configuration (degrees, in particular) more automatically.
    Currently have a hack for HA & normairmass.

    Parameters
    ----------
    value : str
        The column name for the quantity to evaluate. (column name in the database or created by a stacker).
    colmap : dict or None, opt
        A dictionary with a mapping of column names. Default will use OpsimV4 column names.
    runName : str, opt
        The name of the simulated survey. Default is "opsim".
    valueName : str, opt
        The name of the value to be reported in the resultsDb and added to the metric.
        This is intended to help standardize metric comparison between sim versions.
        value = name as it is in the database (seeingFwhmGeom, etc).
        valueName = name to be recorded ('seeingGeom', etc.).  Default is None, which will match 'value'.
    groupName : str, opt
        The group name for this quantity in the displayDict. Default is the same as 'valueName', capitalized.
    extraSql : str, opt
        Additional constraint to add to any sql constraints (e.g. 'propId=1' or 'fieldID=522').
        Default None, for no additional constraints.
    extraMetadata : str, opt
        Additional metadata to add before any below (i.e. "WFD").  Default is None.
    nside : int, opt
        Nside value for healpix slicer. Default 64.
        If "None" is passed, the healpixslicer-based metrics will be skipped.
    filterlist : list of str, opt
        List of the filternames to use for "per filter" evaluation. Default ('u', 'g', 'r', 'i', 'z', 'y').
        If None is passed, the per-filter evaluations will be skipped.

    Returns
    -------
    metricBundleDict
    """
    if colmap is None:
        colmap = ColMapDict('opsimV4')
    bundleList = []

    if valueName is None:
        valueName = value

    if groupName is None:
        groupName = valueName.capitalize()
        subgroup = extraMetadata
    else:
        groupName = groupName.capitalize()
        subgroup = valueName.capitalize()

    if subgroup is None:
        subgroup = 'All visits'

    displayDict = {'group': groupName, 'subgroup': subgroup}

    # Set up basic all and per filter sql constraints.
    filterlist, colors, orders, sqls, metadata = filterList(all=True,
                                                            extraSql=extraSql,
                                                            extraMetadata=extraMetadata)

    # Hack to make HA work, but really I need to account for any stackers/colmaps.
    if value == 'HA':
        stackerList = [stackers.HourAngleStacker(lstCol=colmap['lst'], raCol=colmap['ra'],
                                                 degrees=colmap['raDecDeg'])]
    elif value == 'normairmass':
        stackerList = [stackers.NormAirmassStacker(degrees=colmap['raDecDeg'])]
    else:
        stackerList = None

    # Summarize values over all and per filter (min/mean/median/max/percentiles/outliers/rms).
    slicer = slicers.UniSlicer()
    for f in filterlist:
        for m in extendedMetrics(value, replace_colname=valueName):
            displayDict['caption'] = '%s for %s.' % (m.name, metadata[f])
            displayDict['order'] = orders[f]
            bundle = mb.MetricBundle(m, slicer, sqls[f], stackerList=stackerList,
                                     metadata=metadata[f], displayDict=displayDict)

    # Histogram values over all and per filter.
    for f in filterlist:
        displayDict['caption'] = 'Histogram of %s' % (value)
        if valueName != value:
            displayDict['caption'] += ' (%s)' % (valueName)
        displayDict['caption'] += ' for %s.' % (metadata[f])
        displayDict['order'] = orders[f]
        m = metrics.CountMetric(value, metricName='%s Histogram' % (valueName))
        slicer = slicers.OneDSlicer(sliceColName=value)
        bundle = mb.MetricBundle(m, slicer, sqls[f], stackerList=stackerList,
                                 metadata=metadata[f], displayDict=displayDict)
        bundleList.append(bundle)

    # Make maps of min/median/max for all and per filter, per RA/Dec, with standard summary stats.
    mList = []
    mList.append(metrics.MinMetric(value, metricName='Min %s' % (valueName)))
    mList.append(metrics.MedianMetric(value, metricName='Median %s' % (valueName)))
    mList.append(metrics.MaxMetric(value, metricName='Max %s' % (valueName)))
    slicer = slicers.HealpixSlicer(nside=nside, latCol=colmap['dec'], lonCol=colmap['ra'],
                                   latLonDeg=colmap['raDecDeg'])
    subsetPlots = [plots.HealpixSkyMap(), plots.HealpixHistogram()]
    for f in filterlist:
        for m in mList:
            displayDict['caption'] = 'Map of %s' % m.name
            if valueName != value:
                displayDict['caption'] += ' (%s)' % value
            displayDict['caption'] += ' for %s.' % metadata[f]
            displayDict['order'] = orders[f]
            bundle = mb.MetricBundle(m, slicer, sqls[f], stackerList=stackerList,
                                     metadata=metadata[f], plotFuncs=subsetPlots,
                                     displayDict=displayDict,
                                     summaryMetrics=standardSummary())
            bundleList.append(bundle)

    # Set the runName for all bundles and return the bundleDict.
    for b in bundleList:
        b.setRunName(runName)
    return mb.makeBundlesDictFromList(bundleList)


def allMetadata(colmap=None, runName='opsim', extraSql=None, extraMetadata=None):
    """Generate a large set of metrics about the metadata of each visit -
    distributions of airmass, normalized airmass, seeing, sky brightness, single visit depth,
    hour angle, distance to the moon, and solar elongation.
    The exact metadata which is analyzed is set by the colmap['metadataList'] value.

    Parameters
    ----------
    colmap : dict or None, opt
        A dictionary with a mapping of column names. Default will use OpsimV4 column names.
    runName : str, opt
        The name of the simulated survey. Default is "opsim".
    extraSql : str, opt
        Sql constraint (such as WFD only). Default is None.
    extraMetadata : str, opt
        Metadata to identify the sql constraint (such as WFD). Default is None.

    Returns
    -------
    metricBundleDict
    """

    if colmap is None:
        colmap = ColMapDict('opsimV4')

    bdict = {}

    for valueName in colmap['metadataList']:
        if valueName in colmap:
            value = colmap[valueName]
        else:
            value = valueName
        bdict.update(metadataBasics(value, colmap=colmap, runName=runName,
                                    valueName=valueName,
                                    extraSql=extraSql, extraMetadata=extraMetadata))
    return bdict



