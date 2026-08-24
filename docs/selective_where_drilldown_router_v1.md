# Selective WHERE Drill-down Router V1

The router consumes Evidence Gate candidates but executes no drill-down. Its analysis unit is always `Task Type → WHERE`; it never starts from a school, country, or degree independently.

It groups each task’s eligible segments into a Demand Market Tree: Country is macro geography, School is specific market location, and Degree is a population lens. Strong/Moderate evidence follows the Stable Market route; Emerging signals follow the Growth Source route; Limited High Value evidence follows a revenue-directional route. Weak and Insufficient evidence stop.

At most three candidates per task and route are selected. Remaining evidence stays in the backlog. A Country parent normally plans one child, School; a Degree parent may plan one Geography or School child where it is the stronger entry point. School is terminal by default. Channel, Customer Group, and DDL are deliberately excluded.
