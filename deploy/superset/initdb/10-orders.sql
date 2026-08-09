CREATE TABLE public.orders (
    id integer PRIMARY KEY,
    legacy_status text NOT NULL,
    order_status text NOT NULL,
    amount numeric(10, 2) NOT NULL
);
INSERT INTO public.orders VALUES
    (1, 'pending', 'pending', 10.00),
    (2, 'pending', 'pending', 20.00),
    (3, 'shipped', 'shipped', 30.00),
    (4, 'shipped', 'shipped', 40.00),
    (5, 'delivered', 'delivered', 50.00),
    (6, 'delivered', 'delivered', 60.00);
