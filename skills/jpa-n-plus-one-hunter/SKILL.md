---
name: jpa-n-plus-one-hunter
description: Find and fix N+1 queries and other Hibernate/Spring Data JPA performance traps (eager @ManyToOne, open-in-view, collection fetch + pagination, MultipleBagFetchException) in a Java/Spring codebase. Use when the user asks about slow endpoints, too many SQL queries, lazy loading, LazyInitializationException, entity graphs, JOIN FETCH, or wants a JPA performance review before production.
---

# JPA N+1 hunter

Goal: every request path issues a **bounded, known** number of SQL statements, independent of row count. Prove it with a statement-count assertion. A clean-looking diff is not proof.

## 1. Inventory (read before you change anything)

Run these from the repo root and keep the results in your working notes:

```bash
# entities and their associations
grep -rn --include=*.java -E '@(Entity|OneToMany|ManyToOne|OneToOne|ManyToMany|ElementCollection)' src/main
# explicit fetch settings and graphs
grep -rn --include=*.java -E 'FetchType\.(EAGER|LAZY)|@EntityGraph|@NamedEntityGraph|JOIN FETCH|join fetch|@BatchSize|@Fetch\(' src/main
# repositories
grep -rln --include=*.java -E 'extends (Jpa|Crud|PagingAndSorting|ListCrud)Repository' src/main
# config that hides or enables the problem
grep -rn -E 'open-in-view|default_batch_fetch_size|generate_statistics|show-sql' src/main/resources
```

Build a table: entity → association → declared fetch → **effective** fetch. JPA defaults to remember:

| Annotation | Default fetch | Risk |
|---|---|---|
| `@ManyToOne`, `@OneToOne` | **EAGER** | Each loaded row triggers a select of its parent unless it was join-fetched. This is the classic hidden N+1. |
| `@OneToMany`, `@ManyToMany`, `@ElementCollection` | LAZY | N+1 when iterated in a loop or serialized. |

## 2. Where N+1 actually happens

Trace each read endpoint from controller to repository and flag:

1. **Loops touching a lazy association:** `for (Order o : orders) o.getItems().size()`, streams that `.map(o -> o.getCustomer().getName())`.
2. **Serialization:** Jackson walking lazy associations of an entity returned directly from a controller. This works only because `spring.jpa.open-in-view=true` (the Spring Boot default, which logs a warning at startup) keeps the session open during rendering.
3. **Mappers:** MapStruct/ModelMapper copying an entity graph into a DTO touches every association.
4. **Implicit EAGER `@ManyToOne`** on entities loaded by `findAll`/derived queries. Derived queries don't join-fetch, so Hibernate issues one select per distinct parent.
5. **`@OneToOne` mappedBy (inverse side):** cannot be lazy without bytecode enhancement, so it always loads.
6. **`toString`/`equals`/`hashCode`** (Lombok `@Data` on entities) touching lazy collections.

## 3. Fixes, in order of preference

1. **DTO projection** for read-only views: an interface/record projection or `select new com.x.OrderSummary(o.id, c.name, sum(i.amount)) ... group by`. It does one query and loads no entities. Best for list endpoints.
2. **Fetch what the use case needs, per query:**
   - `@EntityGraph(attributePaths = {"customer", "items"})` on the repository method.
   - or JPQL `select distinct o from Order o join fetch o.customer left join fetch o.items where ...`
3. **Batch fetching** as a global safety net: `spring.jpa.properties.hibernate.default_batch_fetch_size: 50` (or `@BatchSize(size = 50)` on the collection). It turns N+1 into N/50+1. This is a mitigation, not a design.
4. **Make `@ManyToOne` lazy explicitly** (`fetch = FetchType.LAZY`) and fetch it per query where needed.
5. **Set `spring.jpa.open-in-view: false`**, then fix the `LazyInitializationException`s it surfaces by fetching in the service layer. Do this last, on its own commit, because it changes behaviour.

### Traps when applying fixes

- **Collection fetch + pagination:** `join fetch` of a collection with `Pageable` makes Hibernate paginate **in memory** (warning `HHH90003004` / "firstResult/maxResults specified with collection fetch"). Use two queries instead: page the IDs (`select o.id from Order o where ... order by ...` with `Pageable`), then `select distinct o from Order o left join fetch o.items where o.id in :ids`.
- **Two `List` collections fetched at once** throws `MultipleBagFetchException`. Change one to `Set`, or fetch the second collection in a follow-up query. In Hibernate 6, a second query with the same persistence context fills it in.
- **Cartesian products:** fetching two sibling collections multiplies rows. Prefer separate queries or batch fetching.
- **`distinct`:** in Hibernate 6, `distinct` on fetch-join results is applied in memory automatically, so don't rely on SQL `DISTINCT` for entity dedupe.
- Don't switch associations to `EAGER` to "fix" a `LazyInitializationException`. That moves the N+1 to every other query.

## 4. Prove it

Add a test per fixed path that **fails on the old code**. Pick whatever the project already uses, otherwise one of:

- Hibernate statistics: `spring.jpa.properties.hibernate.generate_statistics=true` in the test profile, then
  ```java
  Statistics stats = entityManagerFactory.unwrap(SessionFactory.class).getStatistics();
  stats.clear();
  service.listOrders(PageRequest.of(0, 20));
  assertThat(stats.getPrepareStatementCount()).isLessThanOrEqualTo(2);
  ```
- datasource-proxy / Hypersistence Utils `SQLStatementCountValidator.reset(); ... assertSelectCount(2);`

Seed enough rows (e.g., 20 parents × 3 children) for N+1 to show. Run against Postgres via Testcontainers, not H2, because the plans and SQL differ.

## 5. Report back

For each finding give: file:line, the access path (endpoint → service → association), the statement count before and after, the fix chosen and why the higher-preference fixes didn't fit. Group everything that is only a mitigation (batch size, open-in-view) separately from real fixes.

Logging aid while hunting (local profile only; the pci-shield hook blocks the bind logger at TRACE because it writes bound card data to logs):

```yaml
logging.level.org.hibernate.SQL: DEBUG
```
