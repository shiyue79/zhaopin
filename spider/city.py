import cpca
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import text

def update_addresses_with_province():
    engine = create_engine(
        'mysql+pymysql://root:123456@localhost:3306/zhaopin',
        echo=False,
        pool_pre_ping=True
    )
    query = "SELECT href, location FROM job "
    df = pd.read_sql(query, engine)
    addresses = df['location'].tolist()
    parsed_df = cpca.transform(addresses)
    parsed_df['address'] = parsed_df.apply(
        lambda row: (
            df.iloc[row.name]['location']
            if df.iloc[row.name]['location'].count('-') >= 2
            else f"{row['省']}-{df.iloc[row.name]['location']}"  # 如果少于两个"-"，则添加省份
            if pd.notna(row['省']) and row['省'] is not None
            else df.iloc[row.name]['location']
        ),
        axis=1
    )
    result_df = pd.concat([df, parsed_df[['address']]], axis=1)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            for index, row in result_df.iterrows():
                update_query = text("""
                                    UPDATE job
                                    SET location = :location
                                    WHERE href = :href
                                    """)
                conn.execute(update_query, {'location': row['address'], 'href': row['href']})
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise e
    engine.dispose()
    print(f"成功更新 {len(result_df)} 条记录")

update_addresses_with_province()