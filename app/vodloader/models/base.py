from datetime import datetime, timezone
from pathlib import Path
from typing import Self, List
from vodloader.database import *
from vodloader.util import *
from enum import Enum
import logging


NOT_NULL = 'NOT NULL'

class OrderDirection(Enum):

    ASC = 'ASC'
    DESC = 'DESC'

    def __str__(self) -> str:
        return self.value


class BaseModel(): 
    
    table_name:str = None
    table_command:str = None
    logger: logging.Logger = None
    
    def __init__(self):
        self.logger = logging.getLogger(f'vodloader.models.{type(self).__name__}')

    def _get_extra_attributes(self):
        default_attributes = BaseModel.__dict__
        extra_attributes = []
        for attribute in list(self.__dict__):
            if attribute not in default_attributes:
                extra_attributes.append(attribute)
        return extra_attributes
    
    @classmethod
    async def initialize(cls):
        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(cls.table_command)
        await connection.commit()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

    async def save(self):

        values = []
        attributes = self._get_extra_attributes()
        for attribute in attributes:
            value = self.__getattribute__(attribute)
            match value:
                case Path():
                    value = value.__str__()
                case _:
                     pass
            values.append(value)
        values.extend(values)

        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {self.table_name} 
            ({', '.join(attributes)})
            VALUES
            ({', '.join([db.char for x in attributes])})
            {db.duplicate('id')}
            {', '.join([f'{x}={db.char}' for x in attributes])};
            """,
            values
        )
        await connection.commit()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

    @classmethod
    async def get(
        cls,
        order_by: str = None,
        order: OrderDirection = OrderDirection.ASC,
        **kwargs):

        if not kwargs:
            raise RuntimeError('At least one key must be specified to find a model')

        db = await get_db()

        if order_by:
            order_clause = f'ORDER BY {order_by} {order}'
        else:
            order_clause = ''

        where_clause = 'WHERE'
        values = []
        first_iteration = True
        for key in kwargs:

            if not first_iteration:
                where_clause += ' AND'

            if kwargs[key] == None:
                where_clause += f' {key} IS NULL'
            elif kwargs[key] == NOT_NULL:
                where_clause += f' {key} IS NOT NULL'
            else:
                where_clause += f' {key}={db.char}'
                values.append(kwargs[key])

            first_iteration = False

        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {cls.table_name}
            {where_clause}
            {order_clause};
            """,
            values
        )
        args = await cursor.fetchone()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

        if args:
            return cls(*args)
        else:
            return None
    
    @classmethod
    async def get_many(
        cls,
        order_by: str = None,
        order: OrderDirection = OrderDirection.ASC,
        **kwargs
    ) -> List[Self]:
        db = await get_db()

        if not kwargs:
            raise RuntimeError('At least one key must be specified to find models')

        where_clause = 'WHERE'
        values = []
        for key in kwargs:
            if kwargs[key] == None:
                where_clause += f' {key} IS NULL'
            if kwargs[key] == NOT_NULL:
                where_clause += f' {key} IS NOT NULL'
            else:
                where_clause += f' {key}={db.char}'
                values.append(kwargs[key])
        
        if order_by:
            order_clause = f'ORDER BY {order_by} {order}'
        else:
            order_clause = ''

        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {cls.table_name}
            {where_clause}
            {order_clause};
            """,
            values
        )
        args_list = await cursor.fetchall()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

        if args_list:
            return (cls(*args) for args in args_list)
        else:
            return None

    @classmethod
    async def all(
        cls,
        order_by: str = None,
        order: OrderDirection = OrderDirection.ASC,
    ):
        if order_by:
            order_clause = f'ORDER BY {order_by} {order}'
        else:
            order_clause = ''

        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {cls.table_name}
            {order_clause};
            """
        )
        args_list = await cursor.fetchall()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

        if args_list:
            return (cls(*args) for args in args_list)
        else:
            return None

class EndableModel(BaseModel):

    async def end(self, end: datetime = None):

        if end == None:
            end = datetime.now(timezone.utc)
        
        self.ended_at = end
        await self.save()