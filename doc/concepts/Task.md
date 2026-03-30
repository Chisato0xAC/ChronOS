任务

```json
{
    "id": "string",
    "title": "string",
    "description": "string",
    "type": "main | side | daily",
    
    "status": "pending | processing | completed | cancelled",

    "rewards": [
        {"type": "dp", "amount": 100 },
        {"type": "item", "item_id": "coffee", "amount": 1}
    ],

    "tags": ["string"],

    "start_time": "datetime | null",
    "end_time": "datetime | null",
    "duration_time": "datetime | null",
    "create_at": "datetime",
    "update_at": "datetime"
}
```
