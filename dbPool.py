# -*- coding:utf-8 -*-

"""
date:2017.2.24
@author:xnchall
@version 1.4
	1.0:dbPool()
	1.2:add staticmethod setPool()
	1.3:factor functions
	1.4:fix some bugs: columns(). add function execInsert()  date:2017.3.4
"""

from DBUtils.PooledDB import PooledDB
import sys
import cx_Oracle
import threading
import datetime


class dbPool(object):

	_pool = None

	def __init__(self,db_info={},switch=1):
		"""
		@dbPool __init__
		@switch=1 : get shareConn
		@switch=0 : get privateConn
		"""
		self._pool = dbPool.setPool(db_info)
		if(switch == 0):
			self._conn = self._pool.connection(0)
			print('the privateConn set down!')
		else:
			self._conn = self._pool.connection()
			print('the shareConn set down!')
		self._cursor = self._conn.cursor()
		print('Oracle cursor set down!')

	@staticmethod
	def get_instance(db_info):
		if dbPool._pool is None:
			dbPool._pool = dbPool(db_info)
		else:
			raise TypeError('dbPool could be instantiated only once!')
		return dbPool._pool
		
#	def __new__(cls, *args, **kwargs):
#		if cls._pool is None:
#			cls._pool = super(dbPool, cls).__new__(cls, *args, **kwargs)
#		else:
#			raise TypeError('[%s] could be instantiated only once!'%cls.__name__)
#		return cls._pool


	@staticmethod
	def setPool(db_info):
		"""
		@register DBPool cache
		@set the pool param
		"""
		if dbPool._pool is None:
			print("register a new connection ...")
			print("dbPool is setting ...")
			start = datetime.datetime.now()
			pool = PooledDB(cx_Oracle,
            		user = db_info['user'],
            		password = db_info['passwd'],
            		dsn = "%s:%s/%s" %(db_info['host'],db_info['port'],db_info['dbName']),
            		mincached=2,
            		maxcached=2,
            		maxshared=2,
            		maxconnections=2)
			print("dns = %s:%s/%s" %(db_info['host'],db_info['port'],db_info['dbName']))
			end = datetime.datetime.now()
			print("set dbPool'cache need time: %s s" %(end-start))
			print('set down!')
		return pool

	def columns(self,table):
		"""
		@table: table name
		@return: list
		"""
		sql = ["select lower(column_name)column_name \
        	from all_tab_columns where table_name=upper('%(table)s')"]
		print(''.join(sql) % locals())
		rows = self.execQuery(''.join(sql) % locals())
		columns_list = [k["column_name"] for k in rows]
		return columns_list

	def create_params(self,table,args={}):
		"""
		@table: table name
		@return: list
		"""
		columns_list = self.columns(table)
		params = {}
		for key in columns_list:
			if key in args:
				params[key] = args[key]
		return params

	def get_rows(self, size=None, is_dict = True):
		"""
		@summary:format the result of sql!
		"""
		if size is None:
			rows = self._cursor.fetchall()
		else:
			rows = self._cursor.fetchmany()
		if rows is None:
			rows = []
		if(is_dict):
			dict_rows = []
			dict_keys = [ r[0].lower() for r in self._cursor.description ]
			for row in rows:
				dict_rows.append(dict(zip(dict_keys, row)))
				rows = dict_rows
		return rows

	
	def execute(self,sql,param={}):
		"""@summary:execute sql"""
		try:
			return self._cursor.execute(sql, param)
		except Exception as e:
			self.close()
			print("execute sigle sql arise error")
			raise e

	def executemany(self,sql,param={}):
		"""execute batch sql"""
		try:
			return self._cursor.executemany(sql, param)
		except Exception as e:
			self.close()
			print("execute batch sql arise error")
			raise e

	def execInsertone(self,table,column_dict):
		"""
		@summary:insert one record into DB
		@param table: table
		@param dict: {'user':'user',...}
		"""
		column_dict = self.create_params(table,column_dict)
		keys = ','.join(column_dict.keys())#format
		values = column_dict.values()
		placeholder = ','.join([ ':%s'%(v) for v in column_dict.keys() ])
		in_sql = 'INSERT INTO %(table)s (%(keys)s) VALUES (%(placeholder)s)'
		print(column_dict)
		print(in_sql % locals())
		self.execute(in_sql % locals(), column_dict)
		return self.getRowsNum()


	def execInsertmany(self,table,columns=[],values=()):
		"""
		@summary:insert many records into DB
		@param table:table
		@param columns: ['c1','c2',...]
		@param values: [('1','3',...),('2','4',...)]
		"""
		keys = ','.join(columns)
		placeholder = ','.join([ ':%s'%(v) for v in columns ])
		ins_sql = 'INSERT INTO %(table)s (%(keys)s) VALUES(%(placeholder)s)'
		self.executemany(ins_sql % locals(),values)
		return self.getRowsNum()

	def execQuery(self,sql,param={}):
		self.execute(sql,param)
		#self._cursor.execute(sql)
		return self.get_rows()

	def execInsert(self,sql,param={}):
		"""
		@summary: fix values by hand. insert!
		"""
		self.execute(sql,param)
		return self.getRowsNum()

	def executeUD(self,sql,param={}):
		"""
		@summary: fix values by hand. update and delete!
		"""
		self.execute(sql,param)
		return self.getRowsNum()

	def execQuery_pages(self,sql,args={},page=1,page_size=50):
		_args = args
		count_args = args
		page = int(page)
		next_page =  page * page_size
		cur_page = (page - 1) * page_size
		if((page ==1) or (cur_page) < 0):
			cur_page = 0
			next_page = page_size
		sql = """SELECT * FROM(
		SELECT ROWNUM RN,T.* FROM(""" + sql + """)T 
			WHERE ROWNUM<=:next_page
			)WHERE RN >=:cur_page """
		count_sql = """
			SELECT COUNT(1)CNT FROM (""" + sql + """)"""
		_args["cur_page"] = cur_page
		_args["next_page"] = next_page
		countrows = self.execQuery(count_sql,count_args)
		return rows,countrows[0]['cnt']

	def execUpdate(self,table,set_dict={}, where_dict ={}):
		"""
		@summary:update table
		@param set_dict:set c1=v1 and c2=v2 {'c1':'v1','c2':'v2',...}
		@param cond_dict: where c1=v1 and c2=v2 {'c1':'v1','c2':'v2',...}
		"""
		set_dict = self.create_params(table,set_dict)
		where_dict = self.create_params(table,where_dict)
		set_stmt = ','.join([ '%s=:%s' %(k,k) for k in set_dict.keys() ])
		cond_stmt = ' and '.join([ '%s=:%s' %(k,k) for k in where_dict.keys() ])
		update_sql = 'UPDATE %(table)s set %(set_stmt)s where %(cond_stmt)s'
		comb_args = dict(set_dict,**where_dict)
		print(comb_args)
		print(update_sql % locals())
		self.execute(update_sql % locals(),comb_args)
		return self.getRowsNum()

	def execDelete(self,table,where_dict):
		"""
		@summary:delete data
		@param where_dict:where c1=v1 and c2=v2 {'c1':'v1','c2':'v2',...}
		"""
		where_dict = self.create_params(table,where_dict)
		where_stmt = ' and '.join([ '%s=:%s' %(k,k) for k in where_dict.keys() ])
		del_sql = 'DELETE FROM %(table)s where %(where_stmt)s'
		print(del_sql % locals())
		print(where_dict)
		self.execute(del_sql % locals(), where_dict)
		return self.getRowsNum()

	def execProc(self,proc_name,param=[]):
		"""
		@summary:execute proc
		@proc_name:string
		@param:list,param for proc
		"""
		self._cursor.callproc(proc_name,param)
		return self.getRowsNum()

	def getRowsNum(self):
		"""get records number"""
		return self._cursor.rowcount

	def commit(self):
		"""
		@summary:commit transaction
		"""
		self._conn.commit()

	def rollback(self):
		"""
		@summary:rollback transaction
		"""
		self._conn.rollback()

	def distroyCache(self):
		"""
		@summary:distroy current __init__
		"""
		self.close()

	def close(self,isEnd=1):
		"""
		@summary:close connection
		"""
		self.commit()
		self._cursor.close()
		self._conn.close()

