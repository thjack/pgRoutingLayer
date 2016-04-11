from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
import psycopg2
from .. import pgRoutingLayer_utils as Utils
from FunctionBase import FunctionBase

class Function(FunctionBase):
    
    @classmethod
    def getName(self):
        return 'drivingDistance'
    
    @classmethod
    def getControlNames(self, version):
        if version < 2.1:
            return [
                'labelId', 'lineEditId',
                'labelSource', 'lineEditSource',
                'labelTarget', 'lineEditTarget',
                'labelCost', 'lineEditCost',
                'labelReverseCost', 'lineEditReverseCost',
                'labelSourceId', 'lineEditSourceId', 'buttonSelectSourceId',
                'labelDistance', 'lineEditDistance',
                'checkBoxDirected', 'checkBoxHasReverseCost'
            ]
    
        #Its 2.1 or higher
        return [
            'labelId', 'lineEditId',
            'labelSource', 'lineEditSource',
            'labelTarget', 'lineEditTarget',
            'labelCost', 'lineEditCost',
            'labelReverseCost', 'lineEditReverseCost',
            'labelSourceIds', 'lineEditSourceIds', 'buttonSelectSourceIds',
            'labelDistance', 'lineEditDistance',
            'checkBoxDirected', 'checkBoxHasReverseCost'
        ]
    
    @classmethod
    def isEdgeBase(self):
        return False
    
    @classmethod
    def canExportMerged(self):
        return True

    def isSupportedVersion(self, version):
        return version >= 2.0 and version < 3.0
    
    def prepare(self, canvasItemList):
        resultNodesVertexMarkers = canvasItemList['markers']
        for marker in resultNodesVertexMarkers:
            marker.setVisible(False)
        canvasItemList['markers'] = []
    
    def getQuery(self, args):
        if (args['version'] < 2.1):
            return """
SELECT seq, id1 AS _node, id2 AS _edge, cost AS _cost
FROM pgr_drivingDistance('
  SELECT %(id)s::int4 AS id,
    %(source)s::int4 AS source,
    %(target)s::int4 AS target,
    %(cost)s::float8 AS cost%(reverse_cost)s
  FROM %(edge_table)s
  WHERE %(edge_table)s.%(geometry)s && %(BBOX)s',
  %(source_id)s, %(distance)s,
  %(directed)s, %(has_reverse_cost)s)""" % args

        #2.1 or greater
        #TODO add equicost flag to gui
        return """
SELECT seq, '(' || from_v || ', %(distance)s)' AS path_name,
    from_v AS _from_v,
    node AS _node, edge AS _edge,
    cost AS _cost, agg_cost as _agg_cost
FROM pgr_drivingDistance('
  SELECT %(id)s AS id,
    %(source)s AS source,
    %(target)s AS target,
    %(cost)s AS cost%(reverse_cost)s
  FROM %(edge_table)s
  WHERE %(edge_table)s.%(geometry)s && %(BBOX)s',
  ARRAY[%(source_ids)s]::BIGINT[], %(distance)s,
  %(directed)s, false)
""" % args

    def getExportQuery(self, args):
        args['result_query'] = self.getQuery(args)

        args['with_geom_query'] = """
SELECT result.*,
   ST_X(the_geom) AS x, ST_Y(the_geom) AS y,
   the_geom AS path_geom
FROM %(edge_table)s_vertices_pgr JOIN result
ON %(edge_table)s_vertices_pgr.%(id)s = result._node
""" % args

        msgQuery = """WITH
result AS ( %(result_query)s ),
with_geom AS ( %(with_geom_query)s )
SELECT with_geom.*
FROM with_geom 
ORDER BY seq
""" % args
#SELECT seq, _node, _edge, _cost, x, y, path_geom
        return msgQuery


    def getExportMergeQuery(self, args):
        args['result_query'] = self.getQuery(args)

        query = """
            WITH
            result AS ( %(result_query)s )
            SELECT 
              CASE
                WHEN result._node = %(edge_table)s.%(source)s
                  THEN %(edge_table)s.%(geometry)s
                ELSE ST_Reverse(%(edge_table)s.%(geometry)s)
              END AS path_geom,
              result.*, %(edge_table)s.*
            FROM %(edge_table)s JOIN result
            ON %(edge_table)s.%(id)s = result._edge ORDER BY result.seq
            """ % args

        return query






    def draw(self, rows, con, args, geomType, canvasItemList, mapCanvas):
        resultNodesVertexMarkers = canvasItemList['markers']
        table =  """%(edge_table)s_vertices_pgr""" % args
        srid, geomType = Utils.getSridAndGeomType(con, table, 'the_geom')
        Utils.setTransformQuotes(args,srid, args['canvas_srid'])

        for row in rows:
            cur2 = con.cursor()
            if args['version'] < 2.1:
                args['result_node_id'] = row[1]
                args['result_edge_id'] = row[2]
                args['result_cost'] = row[3]
            else:
                args['result_node_id'] = row[3]
                args['result_edge_id'] = row[4]
                args['result_cost'] = row[5]

            query2 = """
                    SELECT ST_AsText(%(transform_s)s the_geom %(transform_e)s)
                    FROM %(edge_table)s_vertices_pgr
                    WHERE  id = %(result_node_id)d
                    """ % args
            cur2.execute(query2)
            row2 = cur2.fetchone()
            if (row2):
                geom = QgsGeometry().fromWkt(str(row2[0]))
                pt = geom.asPoint()
                vertexMarker = QgsVertexMarker(mapCanvas)
                vertexMarker.setColor(Qt.red)
                vertexMarker.setPenWidth(2)
                vertexMarker.setIconSize(5)
                vertexMarker.setCenter(QgsPoint(pt))
                resultNodesVertexMarkers.append(vertexMarker)

    def __init__(self, ui):
        FunctionBase.__init__(self, ui)
