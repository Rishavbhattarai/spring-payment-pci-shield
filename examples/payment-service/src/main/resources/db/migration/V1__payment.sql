create table payment (
    id          uuid primary key,
    amount      numeric(19, 4) not null,
    currency    char(3)        not null,
    status      varchar(20)    not null,
    pan_last4   char(4)        not null,
    gateway_ref varchar(64),
    created_at  timestamptz    not null
);
