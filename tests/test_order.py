import uuid
import json
from peewee import SqliteDatabase
from http.client import OK, NOT_FOUND, NO_CONTENT, CREATED, BAD_REQUEST

from app import app
from models import Order, OrderItem, Item, User


class TestOrders:
    @classmethod
    def setup_class(cls):
        database = SqliteDatabase(':memory:')

        tables = [OrderItem, Order, Item, User]
        for table in tables:
            table._meta.database = database
            table.create_table()

        cls.user1 = User.create(
            uuid=str(uuid.uuid4()),
            first_name='Name',
            last_name='Surname',
            email='email@domain.com',
            password='password',
        )
        cls.item1 = Item.create(
            uuid=str(uuid.uuid4()),
            name='Item one',
            price=10,
            description='Item one description',
            category='Category one',
        )
        cls.item2 = Item.create(
            uuid=str(uuid.uuid4()),
            name='Item two',
            price=10,
            description='Item two description',
            category='Category one',
        )

        app.config['TESTING'] = True
        cls.app = app.test_client()

    def setup_method(self):
        OrderItem.delete().execute()
        Order.delete().execute()

    def test_get_orders__empty(self):
        resp = self.app.get('/orders/')
        assert resp.status_code == OK
        assert json.loads(resp.data.decode()) == []

    def test_get_orders(self):
        order1 = Order.create(
            uuid=uuid.uuid4(),
            total_price=10,
            user=self.user1.id,
        )
        OrderItem.create(
            order=order1.id,
            item=self.item1.id,
            quantity=1,
            subtotal=self.item1.price,
        )

        order2 = Order.create(
            uuid=uuid.uuid4(),
            total_price=7,
            user=self.user1.id,
        )
        OrderItem.create(
            order=order2.id,
            item=self.item1.id,
            quantity=1,
            subtotal=self.item1.price,
        )

        resp = self.app.get('/orders/')
        assert resp.status_code == OK
        assert json.loads(resp.data.decode()) == [order1.json(), order2.json()]

    def test_create_order__success(self):
        new_order_data = {
            'user': self.user1.uuid,
            'items': json.dumps([
                [self.item1.uuid, 2], [self.item2.uuid, 1]
            ])
        }

        resp = self.app.post('/orders/', data=new_order_data)
        assert resp.status_code == CREATED

        order_from_server = json.loads(resp.data.decode())
        order_from_db = Order.get(Order.uuid == order_from_server['uuid']).json()

        assert len(Order.select()) == 1
        assert order_from_db == order_from_server

        order_from_server.pop('uuid')
        assert order_from_server['user'] == new_order_data['user']
        assert len(order_from_server['items']) == 2

        order_items_ids = [self.item1.uuid, self.item2.uuid]
        assert order_from_server['items'][0]['uuid'] in order_items_ids
        assert order_from_server['items'][1]['uuid'] in order_items_ids

        order_total = (self.item1.price * 2) + self.item2.price
        assert order_from_server['total_price'] == order_total

    def test_create_order__failure_missing_field(self):
        new_order_data = {
            'user': self.user1.uuid
        }

        resp = self.app.post('/orders/', data=new_order_data)
        assert resp.status_code == BAD_REQUEST
        assert len(Order.select()) == 0

    def test_create_order__failure_empty_items(self):
        new_order_data = {
            'user': self.user1.uuid,
            'items': json.dumps('')
        }

        resp = self.app.post('/orders/', data=new_order_data)
        assert resp.status_code == BAD_REQUEST
        assert len(Order.select()) == 0

    def test_create_order__failure_non_existing_items(self):
        new_order_data = {
            'user': self.user1.uuid,
            'items': json.dumps([
                [str(uuid.uuid4()), 1], [str(uuid.uuid4()), 1]
            ])
        }

        resp = self.app.post('/orders/', data=new_order_data)
        assert resp.status_code == BAD_REQUEST
        assert len(Order.select()) == 0

    def test_create_order__failure_non_existing_user(self):
        new_order_data = {
            'user': str(uuid.uuid4()),
            'items': json.dumps([
                [self.item1.uuid, 1]
            ])
        }

        resp = self.app.post('/orders/', data=new_order_data)
        assert resp.status_code == BAD_REQUEST
        assert len(Order.select()) == 0

    def test_modify_order__success(self):
        order1 = Order.create(
            uuid=uuid.uuid4(),
            total_price=10,
            user=self.user1.id,
        )
        OrderItem.create(
            order=order1.id,
            item=self.item1.id,
            quantity=1,
            subtotal=self.item1.price,
        )

        order2 = Order.create(
            uuid=uuid.uuid4(),
            total_price=12,
            user=self.user1.id,
        )
        OrderItem.create(
            order=order2.id,
            item=self.item1.id,
            quantity=1,
            subtotal=self.item1.price,
        )

        updates = {
            'items': json.dumps([
                    [self.item2.uuid, 2]
                ])
        }

        resp = self.app.put(
            '/orders/{}'.format(order1.uuid),
            data=updates
        )
        assert resp.status_code == OK

        order1_upd = Order.get(Order.uuid == order1.uuid).json()
        total_price = self.item2.price*2
        assert order1_upd['total_price'] == total_price

        order2_db = Order.get(Order.uuid == order2.uuid).json()
        assert order2_db == order2.json()

        order1_items = OrderItem.select().where(OrderItem.order_id == order1.id)
        assert len(order1_items) == 1
        assert str(order1_items[0].item.uuid) == self.item2.uuid

    def test_modify_order__failure_non_existing(self):
        Order.create(
            uuid=str(uuid.uuid4()),
            total_price=10,
            user=self.user1.id,
        )

        updates = {
            'items': json.dumps([
                    [self.item1.uuid, 1]
                ])
        }

        resp = self.app.put(
            '/orders/{}'.format(str(uuid.uuid4())),
            data=updates
        )
        assert resp.status_code == NOT_FOUND

    def test_modify_order__failure_non_existing_empty_orders(self):
        updates = {
            'items': json.dumps([
                    [self.item1.uuid, 1]
                ])
        }

        resp = self.app.put(
            '/orders/{}'.format(str(uuid.uuid4())),
            data=updates
        )
        assert resp.status_code == NOT_FOUND

    def test_modify_order__failure_changed_uuid(self):
        order1 = Order.create(
            uuid=str(uuid.uuid4()),
            total_price=10,
            user=self.user1.id,
        )

        updates = {
            'uuid': str(uuid.uuid4())
        }

        resp = self.app.put(
            '/orders/{}'.format(order1.uuid),
            data=updates
        )
        assert resp.status_code == BAD_REQUEST

    def test_modify_order__failure_changed_user(self):
        order1 = Order.create(
            uuid=str(uuid.uuid4()),
            total_price=10,
            user=self.user1.id,
        )

        updates = {
            'user': str(uuid.uuid4())
        }

        resp = self.app.put(
            '/orders/{}'.format(order1.uuid),
            data=updates
        )
        assert resp.status_code == BAD_REQUEST

    def test_modify_order__failure_empty_field(self):
        order1 = Order.create(
            uuid=str(uuid.uuid4()),
            total_price=10,
            user=self.user1.id,
        )

        updates = {
            'items': json.dumps('')
        }

        resp = self.app.put(
            '/orders/{}'.format(order1.uuid),
            data=updates
        )
        assert resp.status_code == BAD_REQUEST

    def test_delete_order__success(self):
        order1 = Order.create(
            uuid=uuid.uuid4(),
            total_price=10,
            user=self.user1,
        )
        OrderItem.create(
            order=order1.id,
            item=self.item1.id,
            quantity=1,
            subtotal=self.item1.price,
        )

        order2 = Order.create(
            uuid=uuid.uuid4(),
            total_price=12,
            user=self.user1,
        )
        OrderItem.create(
            order=order2.id,
            item=self.item1.id,
            quantity=1,
            subtotal=self.item1.price,
        )

        resp = self.app.delete('/orders/{}'.format(order1.uuid))
        assert resp.status_code == NO_CONTENT

        orders = Order.select()
        assert len(orders) == 1
        assert Order.get(Order.uuid == order2.uuid)

        order_items = OrderItem.select().where(OrderItem.order_id == order1.id)
        assert len(order_items) == 0

    def test_delete_order__failure_non_existing(self):
        Order.create(
            uuid=str(uuid.uuid4()),
            total_price=10,
            user=self.user1.id
        )
        Order.create(
            uuid=str(uuid.uuid4()),
            total_price=12,
            user=self.user1.id
        )

        resp = self.app.delete('/orders/{}'.format(str(uuid.uuid4())))
        assert resp.status_code == NOT_FOUND
        assert len(Order.select()) == 2

    def test_delete_order__failure_non_existing_empty_orders(self):
        resp = self.app.delete('/orders/{}'.format(str(uuid.uuid4())))
        assert resp.status_code == NOT_FOUND
